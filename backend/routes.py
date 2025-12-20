from fastapi import APIRouter, HTTPException, Depends, Request, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import Optional, List, Dict
import logging
import sys

# Import services
from llm_service import llm_service
from fine_tuning_service import FineTuningService
from feedback_service import FeedbackService
from pattern_analysis_service import PatternAnalysisService
from semantic_search_service import SemanticSearchService

# Import authentication
from auth import verify_api_key

# Import rate limiting
from rate_limit import limiter_with_api_key, STRICT_RATE_LIMIT, DEFAULT_RATE_LIMIT

# Create router first
router = APIRouter()

# Import models and dependencies from app (after router creation to avoid circular import)
# This will work because app.py imports routes at the end, after all models are defined
import app

# Get references from app module
get_db = app.get_db
AgentTask = app.AgentTask
AgentConversation = app.AgentConversation
TaskCreate = app.TaskCreate
TaskResponse = app.TaskResponse
ConversationCreate = app.ConversationCreate
ConversationResponse = app.ConversationResponse
FeedbackCreate = app.FeedbackCreate
FeedbackResponse = app.FeedbackResponse
FeedbackStats = app.FeedbackStats

# Task endpoints
@router.post("/tasks", response_model=TaskResponse)
@limiter_with_api_key.limit(DEFAULT_RATE_LIMIT)
async def create_task(
    request: Request,
    task: TaskCreate, 
    db: Session = Depends(get_db),
    api_key: str = Depends(verify_api_key)
):
    db_task = AgentTask(
        task_name=task.task_name,
        description=task.description,
        status="pending"
    )
    db.add(db_task)
    db.commit()
    db.refresh(db_task)
    return db_task

@router.get("/tasks", response_model=List[TaskResponse])
async def get_tasks(
    skip: int = 0, 
    limit: int = 100, 
    db: Session = Depends(get_db),
    api_key: str = Depends(verify_api_key)
):
    tasks = db.query(AgentTask).offset(skip).limit(limit).all()
    return tasks

@router.get("/tasks/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: int, 
    db: Session = Depends(get_db),
    api_key: str = Depends(verify_api_key)
):
    task = db.query(AgentTask).filter(AgentTask.id == task_id).first()
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task

@router.put("/tasks/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: int, 
    status: str, 
    result: Optional[str] = None, 
    db: Session = Depends(get_db),
    api_key: str = Depends(verify_api_key)
):
    from datetime import datetime
    task = db.query(AgentTask).filter(AgentTask.id == task_id).first()
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    task.status = status
    if result:
        task.result = result
    task.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(task)
    return task

# Helper function để index conversation trong background
async def index_conversation_background(
    conversation_id: int,
    user_message: str,
    ai_response: str
):
    """
    Background task để index conversation (tạo embeddings)
    Chạy sau khi response đã được trả về cho client
    """
    try:
        # Tạo database session mới cho background task
        from app import SessionLocal
        db = SessionLocal()
        try:
            semantic_service = SemanticSearchService(db)
            indexing_result = await semantic_service.index_conversation(
                conversation_id=conversation_id,
                user_message=user_message,
                ai_response=ai_response
            )
            if not indexing_result.get("success"):
                logging.warning(f"Failed to index conversation {conversation_id}: {indexing_result.get('error')}")
        finally:
            db.close()
    except Exception as e:
        logging.error(f"Error indexing conversation {conversation_id} in background: {e}")

# Conversation endpoints
@router.post("/conversations", response_model=ConversationResponse)
@limiter_with_api_key.limit(STRICT_RATE_LIMIT)
async def create_conversation(
    request: Request,
    conversation: ConversationCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    api_key: str = Depends(verify_api_key)
):
    """
    Tạo conversation mới với AI response từ LLM (llama3.1)
    """
    try:
        # Lấy conversation history nếu có session_id
        conversation_history = []
        if conversation.session_id:
            previous_convs = db.query(AgentConversation).filter(
                AgentConversation.session_id == conversation.session_id
            ).order_by(AgentConversation.created_at).all()
            
            for conv in previous_convs:
                conversation_history.append({
                    "role": "user",
                    "content": conv.user_message
                })
                if conv.ai_response:
                    conversation_history.append({
                        "role": "assistant",
                        "content": conv.ai_response
                    })
        
        # Semantic search để tìm similar conversations
        semantic_service = SemanticSearchService(db)
        semantic_context = await semantic_service.get_semantic_context(
            user_message=conversation.user_message,
            context_limit=3
        )
        
        # Phân tích patterns và tìm suggestions
        pattern_service = PatternAnalysisService(db)
        suggestions = pattern_service.get_response_suggestions(
            conversation.user_message,
            use_patterns=True
        )
        
        # Kết hợp semantic search results với pattern suggestions
        if semantic_context:
            # Thêm semantic results vào suggestions
            suggestions["semantic_matches"] = semantic_context
        
        # Tìm best response từ semantic search
        best_response = await semantic_service.find_best_response(
            user_message=conversation.user_message,
            limit=1,
            min_similarity=0.7
        )
        
        # Tạo enhanced system prompt với pattern insights và semantic context
        pattern_insights = {
            "insights": suggestions.get("common_patterns", {}),
            "recommended_approach": suggestions.get("recommended_approach")
        }
        
        system_prompt = llm_service.get_system_prompt(
            use_fine_tuned=False,
            pattern_insights=pattern_insights if suggestions.get("recommended_approach") else None
        )
        
        # Thêm semantic context vào prompt nếu có
        if semantic_context and len(semantic_context) > 0:
            context_text = "\n\nCác conversations tương tự đã có:\n"
            for i, ctx in enumerate(semantic_context[:2], 1):  # Top 2
                context_text += f"{i}. User: {ctx['user_message'][:100]}...\n"
                context_text += f"   Assistant: {ctx['ai_response'][:150]}...\n"
            system_prompt += context_text
        
        # Nếu có best response với high confidence, tham khảo
        if best_response and best_response.get("confidence") == "high":
            system_prompt += f"\n\nTham khảo response tốt (similarity: {best_response['similarity']:.2f}): {best_response['suggested_response'][:200]}"
        
        # Generate AI response từ LLM
        ai_response = await llm_service.generate_response(
            user_message=conversation.user_message,
            conversation_history=conversation_history if conversation_history else None,
            system_prompt=system_prompt
        )
        
        # Lưu vào database
        db_conversation = AgentConversation(
            user_message=conversation.user_message,
            ai_response=ai_response,
            session_id=conversation.session_id
        )
        db.add(db_conversation)
        db.commit()
        db.refresh(db_conversation)
        
        # Index conversation trong background (không block response)
        # Background task sẽ chạy sau khi response đã được trả về cho client
        background_tasks.add_task(
            index_conversation_background,
            conversation_id=db_conversation.id,
            user_message=conversation.user_message,
            ai_response=ai_response
        )
        
        return db_conversation
    except Exception as e:
        logging.error(f"Error creating conversation: {e}")
        raise HTTPException(status_code=500, detail=f"Error generating response: {str(e)}")

@router.get("/conversations", response_model=List[ConversationResponse])
async def get_conversations(
    session_id: Optional[str] = None, 
    skip: int = 0, 
    limit: int = 100, 
    db: Session = Depends(get_db),
    api_key: str = Depends(verify_api_key)
):
    query = db.query(AgentConversation)
    if session_id:
        query = query.filter(AgentConversation.session_id == session_id)
    conversations = query.order_by(AgentConversation.created_at.desc()).offset(skip).limit(limit).all()
    return conversations

# LLM Management endpoints
@router.get("/api/llm/status")
async def get_llm_status(api_key: str = Depends(verify_api_key)):
    """Kiểm tra trạng thái LLM connection"""
    ollama_status = await llm_service.check_ollama_connection()
    return {
        "provider": llm_service.provider,
        "model": llm_service.model_name,
        "ollama_base_url": llm_service.ollama_base_url,
        "ollama_status": ollama_status
    }

# Fine-tuning endpoints
@router.get("/api/finetune/stats")
async def get_finetune_stats(
    db: Session = Depends(get_db),
    api_key: str = Depends(verify_api_key)
):
    """Lấy thống kê về dữ liệu training"""
    ft_service = FineTuningService(db)
    return ft_service.get_training_stats()

@router.post("/api/finetune/export")
@limiter_with_api_key.limit(STRICT_RATE_LIMIT)
async def export_training_data(
    request: Request,
    session_id: Optional[str] = None,
    format: str = "jsonl",
    min_conversations: int = 10,
    use_feedback: bool = True,
    min_rating: int = 3,
    include_corrections: bool = True,
    db: Session = Depends(get_db),
    api_key: str = Depends(verify_api_key)
):
    """
    Export conversations để tạo training data cho fine-tuning
    
    Args:
        session_id: Filter theo session (None = tất cả)
        format: jsonl, json, txt, hoặc ollama
        min_conversations: Số lượng conversations tối thiểu
        use_feedback: Có sử dụng feedback để cải thiện training data không
        min_rating: Rating tối thiểu để include (nếu dùng feedback)
        include_corrections: Có include user corrections không
    """
    ft_service = FineTuningService(db)
    
    # Ưu tiên sử dụng feedback nếu có
    if use_feedback:
        if format == "ollama":
            result = ft_service.create_ollama_finetune_with_feedback(
                use_feedback=True,
                min_rating=min_rating,
                include_corrections=include_corrections
            )
        else:
            result = ft_service.export_with_feedback(
                use_feedback=True,
                min_rating=min_rating,
                include_corrections=include_corrections,
                output_format=format
            )
        
        # Nếu không có feedback data, fallback to normal export
        if not result.get("success") and "feedback" in result.get("message", "").lower():
            logging.info("No feedback data, falling back to normal export")
            use_feedback = False
    
    # Fallback to normal export
    if not use_feedback:
        if format == "ollama":
            result = ft_service.create_ollama_finetune_data(session_id, min_conversations)
        else:
            result = ft_service.export_conversations_for_training(session_id, min_conversations, format)
    
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("message") or result.get("error"))
    
    return result

@router.get("/api/finetune/instructions")
async def get_finetune_instructions(
    db: Session = Depends(get_db),
    api_key: str = Depends(verify_api_key)
):
    """Lấy hướng dẫn fine-tuning"""
    ft_service = FineTuningService(db)
    return {
        "instructions": ft_service.prepare_finetune_instructions()
    }

# Feedback endpoints
@router.post("/api/feedback", response_model=Dict)
@limiter_with_api_key.limit(DEFAULT_RATE_LIMIT)
async def submit_feedback(
    request: Request,
    feedback: FeedbackCreate,
    db: Session = Depends(get_db),
    api_key: str = Depends(verify_api_key)
):
    """
    Submit feedback cho một conversation
    
    - rating: 1-5 stars (hoặc -1 cho thumbs down, 1 cho thumbs up)
    - feedback_type: rating, thumbs_up, thumbs_down, detailed
    - comment: Comment chi tiết
    - user_correction: Câu trả lời đúng nếu user muốn sửa
    - is_helpful: yes, no, partially
    """
    fb_service = FeedbackService(db)
    result = fb_service.submit_feedback(
        conversation_id=feedback.conversation_id,
        rating=feedback.rating,
        feedback_type=feedback.feedback_type,
        comment=feedback.comment,
        user_correction=feedback.user_correction,
        is_helpful=feedback.is_helpful
    )
    
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error"))
    
    return result

@router.get("/api/feedback/stats", response_model=FeedbackStats)
async def get_feedback_stats(
    conversation_id: Optional[int] = None,
    db: Session = Depends(get_db),
    api_key: str = Depends(verify_api_key)
):
    """Lấy thống kê feedback"""
    fb_service = FeedbackService(db)
    stats = fb_service.get_feedback_stats(conversation_id)
    return FeedbackStats(**stats)

@router.get("/api/feedback/conversations")
async def get_conversations_with_feedback(
    rating_threshold: Optional[int] = None,
    limit: int = 100,
    db: Session = Depends(get_db),
    api_key: str = Depends(verify_api_key)
):
    """Lấy conversations kèm feedback để review"""
    fb_service = FeedbackService(db)
    conversations = fb_service.get_conversations_with_feedback(
        rating_threshold=rating_threshold,
        limit=limit
    )
    return conversations

@router.get("/api/feedback/training-data")
async def get_feedback_for_training(
    min_rating: int = 3,
    include_corrections: bool = True,
    db: Session = Depends(get_db),
    api_key: str = Depends(verify_api_key)
):
    """Lấy feedback để sử dụng trong training/fine-tuning"""
    fb_service = FeedbackService(db)
    training_data = fb_service.get_feedback_for_training(
        min_rating=min_rating,
        include_corrections=include_corrections
    )
    return {
        "count": len(training_data),
        "data": training_data
    }

# Pattern Analysis endpoints
@router.get("/api/patterns/insights")
async def get_pattern_insights(
    db: Session = Depends(get_db),
    api_key: str = Depends(verify_api_key)
):
    """Lấy tổng hợp insights từ pattern analysis"""
    pattern_service = PatternAnalysisService(db)
    return pattern_service.get_pattern_insights()

@router.get("/api/patterns/common-questions")
async def get_common_questions(
    min_frequency: int = 2,
    limit: int = 20,
    db: Session = Depends(get_db),
    api_key: str = Depends(verify_api_key)
):
    """Lấy danh sách câu hỏi thường gặp"""
    pattern_service = PatternAnalysisService(db)
    return pattern_service.analyze_common_questions(
        min_frequency=min_frequency,
        limit=limit
    )

@router.get("/api/patterns/topics")
async def get_topics(
    min_occurrences: int = 3,
    limit: int = 15,
    db: Session = Depends(get_db),
    api_key: str = Depends(verify_api_key)
):
    """Lấy danh sách topics phổ biến"""
    pattern_service = PatternAnalysisService(db)
    return pattern_service.analyze_topics(
        min_occurrences=min_occurrences,
        limit=limit
    )

@router.get("/api/patterns/intents")
async def get_user_intents(
    limit: int = 10,
    db: Session = Depends(get_db),
    api_key: str = Depends(verify_api_key)
):
    """Lấy phân tích user intents"""
    pattern_service = PatternAnalysisService(db)
    return pattern_service.analyze_user_intents(limit=limit)

@router.get("/api/patterns/response-patterns")
async def get_response_patterns(
    min_rating: int = 4,
    db: Session = Depends(get_db),
    api_key: str = Depends(verify_api_key)
):
    """Lấy phân tích response patterns tốt/xấu"""
    pattern_service = PatternAnalysisService(db)
    return pattern_service.analyze_response_patterns(min_rating=min_rating)

@router.get("/api/patterns/similar")
async def find_similar_conversations(
    user_message: str,
    limit: int = 5,
    min_rating: Optional[int] = None,
    db: Session = Depends(get_db),
    api_key: str = Depends(verify_api_key)
):
    """Tìm conversations tương tự"""
    pattern_service = PatternAnalysisService(db)
    return pattern_service.find_similar_conversations(
        user_message=user_message,
        limit=limit,
        min_rating=min_rating
    )

@router.get("/api/patterns/suggestions")
async def get_response_suggestions(
    user_message: str,
    use_patterns: bool = True,
    db: Session = Depends(get_db),
    api_key: str = Depends(verify_api_key)
):
    """Lấy suggestions cho response dựa trên patterns"""
    pattern_service = PatternAnalysisService(db)
    return pattern_service.get_response_suggestions(
        user_message=user_message,
        use_patterns=use_patterns
    )

# Semantic Search endpoints
@router.get("/api/semantic/search")
async def semantic_search(
    query: str,
    limit: int = 5,
    min_similarity: float = 0.5,
    filter_by_rating: Optional[int] = None,
    db: Session = Depends(get_db),
    api_key: str = Depends(verify_api_key)
):
    """
    Tìm kiếm ngữ nghĩa conversations tương tự
    
    Args:
        query: Text cần tìm
        limit: Số lượng kết quả
        min_similarity: Độ tương tự tối thiểu (0-1)
        filter_by_rating: Filter theo rating tối thiểu
    """
    semantic_service = SemanticSearchService(db)
    results = await semantic_service.search_similar_conversations(
        query_text=query,
        limit=limit,
        min_similarity=min_similarity,
        filter_by_rating=filter_by_rating
    )
    return {
        "query": query,
        "count": len(results),
        "results": results
    }

@router.get("/api/semantic/best-response")
async def get_best_response(
    user_message: str,
    min_similarity: float = 0.6,
    db: Session = Depends(get_db),
    api_key: str = Depends(verify_api_key)
):
    """Tìm best response cho user message"""
    semantic_service = SemanticSearchService(db)
    result = await semantic_service.find_best_response(
        user_message=user_message,
        min_similarity=min_similarity
    )
    return result if result else {"message": "No similar high-rated conversation found"}

@router.post("/api/semantic/index/{conversation_id}")
async def index_conversation(
    conversation_id: int,
    db: Session = Depends(get_db),
    api_key: str = Depends(verify_api_key)
):
    """Index conversation (tạo embeddings)"""
    # Lấy conversation
    conv = db.query(AgentConversation).filter(
        AgentConversation.id == conversation_id
    ).first()
    
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    semantic_service = SemanticSearchService(db)
    result = await semantic_service.index_conversation(
        conversation_id=conversation_id,
        user_message=conv.user_message,
        ai_response=conv.ai_response
    )
    
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error"))
    
    return result

@router.get("/api/semantic/indexing-stats")
async def get_indexing_stats(
    db: Session = Depends(get_db),
    api_key: str = Depends(verify_api_key)
):
    """Lấy thống kê về indexing"""
    semantic_service = SemanticSearchService(db)
    return semantic_service.get_indexing_stats()

@router.post("/api/semantic/reindex-all")
@limiter_with_api_key.limit(STRICT_RATE_LIMIT)
async def reindex_all_conversations(
    request: Request,
    limit: Optional[int] = None,
    db: Session = Depends(get_db),
    api_key: str = Depends(verify_api_key)
):
    """Re-index tất cả conversations (background task)"""
    # Lấy conversations chưa có embeddings
    query = """
        SELECT ac.id, ac.user_message, ac.ai_response
        FROM agent_conversations ac
        LEFT JOIN conversation_embeddings ce ON ac.id = ce.conversation_id
        WHERE ce.id IS NULL
        ORDER BY ac.created_at DESC
    """
    
    if limit:
        query += f" LIMIT {limit}"
    
    conversations = db.execute(text(query)).fetchall()
    
    semantic_service = SemanticSearchService(db)
    indexed = 0
    errors = 0
    
    for conv_id, user_msg, ai_resp in conversations:
        try:
            result = await semantic_service.index_conversation(
                conversation_id=conv_id,
                user_message=user_msg,
                ai_response=ai_resp
            )
            if result.get("success"):
                indexed += 1
            else:
                errors += 1
        except Exception as e:
            logging.error(f"Error indexing conversation {conv_id}: {e}")
            errors += 1
    
    return {
        "total_processed": len(conversations),
        "indexed": indexed,
        "errors": errors
    }

@router.get("/api/embedding/status")
async def get_embedding_status(api_key: str = Depends(verify_api_key)):
    """Kiểm tra trạng thái embedding service"""
    from embedding_service import embedding_service
    status = await embedding_service.check_embedding_service()
    return status