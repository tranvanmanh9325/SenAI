from fastapi import APIRouter, HTTPException, Depends, Request
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import Optional, List, Dict
import logging

# Import services
from services.feedback_service import FeedbackService
from services.pattern_analysis_service import PatternAnalysisService
from services.semantic_search_service import SemanticSearchService

# Import authentication
from middleware.auth import verify_api_key

# Import rate limiting
from middleware.rate_limit import limiter_with_api_key, STRICT_RATE_LIMIT, DEFAULT_RATE_LIMIT

# Create router
router = APIRouter()

# Import models and dependencies from app (after router creation to avoid circular import)
import app

# Get references from app module
get_db = app.get_db
AgentConversation = app.AgentConversation
FeedbackCreate = app.FeedbackCreate
FeedbackStats = app.FeedbackStats

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
    from services.embedding_service import embedding_service
    status = await embedding_service.check_embedding_service()
    return status

