from fastapi import APIRouter, HTTPException, Depends, Request, BackgroundTasks
from sqlalchemy.orm import Session
from typing import Optional, List
import logging

# Import services
from services.llm_service import llm_service
from services.fine_tuning_service import FineTuningService
from services.pattern_analysis_service import PatternAnalysisService
from services.semantic_search_service import SemanticSearchService

# Import authentication
from middleware.auth import verify_api_key

# Import rate limiting
from middleware.rate_limit import limiter_with_api_key, STRICT_RATE_LIMIT, DEFAULT_RATE_LIMIT

# Create router first
router = APIRouter()

# Import models from models.py to avoid circular imports
from models import AgentTask, AgentConversation

# Import dependencies from app
import app

# Get references from app module
get_db = app.get_db
TaskCreate = app.TaskCreate
TaskResponse = app.TaskResponse
ConversationCreate = app.ConversationCreate
ConversationResponse = app.ConversationResponse

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
        import sys
        import os
        # Add parent directory to path để import app
        parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if parent_dir not in sys.path:
            sys.path.insert(0, parent_dir)
        from app import SessionLocal  # SessionLocal is still in app.py
        db = SessionLocal()
        try:
            from services.semantic_search_service import SemanticSearchService
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