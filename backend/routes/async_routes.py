"""
Async Routes
Các routes sử dụng async database operations
"""
from fastapi import APIRouter, HTTPException, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional, List
import logging

# Import services
from services.llm_service import llm_service
from services.async_cache_service import get_async_cache_service
from services.celery_tasks import index_conversation_task
from services.batch_processing import batch_processor

# Import centralized error handler
from services.error_handler import (
    handle_error, handle_database_error, handle_llm_error,
    handle_validation_error, ErrorCategory, ErrorSeverity
)

# Import authentication
from middleware.auth import verify_api_key

# Import rate limiting
from middleware.rate_limit import limiter_with_api_key, STRICT_RATE_LIMIT, DEFAULT_RATE_LIMIT

# Import async helpers
from services.async_helpers import run_sync_in_thread

# Import models
from config.models import AgentTask, AgentConversation

# Import dependencies from app
import app

# Get references from app module
get_async_db = app.get_async_db
TaskCreate = app.TaskCreate
TaskResponse = app.TaskResponse
ConversationCreate = app.ConversationCreate
ConversationResponse = app.ConversationResponse

# Create router
async_router = APIRouter(prefix="/async", tags=["async"])

logger = logging.getLogger(__name__)


# Async Task endpoints
@async_router.post("/tasks", response_model=TaskResponse)
@limiter_with_api_key.limit(DEFAULT_RATE_LIMIT)
async def create_task_async(
    request: Request,
    task: TaskCreate,
    db: AsyncSession = Depends(get_async_db),
    api_key = Depends(verify_api_key)
):
    """Create task với async database operations"""
    try:
        db_task = AgentTask(
            task_name=task.task_name,
            description=task.description,
            status="pending"
        )
        db.add(db_task)
        await db.commit()
        await db.refresh(db_task)
        return db_task
    except Exception as e:
        await db.rollback()
        raise handle_database_error(e, context="create_task_async")


@async_router.get("/tasks", response_model=List[TaskResponse])
async def get_tasks_async(
    request: Request,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_async_db),
    api_key = Depends(verify_api_key)
):
    """Get tasks với async database operations"""
    try:
        stmt = select(AgentTask).offset(skip).limit(limit)
        result = await db.execute(stmt)
        tasks = result.scalars().all()
        return tasks
    except Exception as e:
        raise handle_database_error(e, context="get_tasks_async")


@async_router.get("/tasks/{task_id}", response_model=TaskResponse)
async def get_task_async(
    request: Request,
    task_id: int,
    db: AsyncSession = Depends(get_async_db),
    api_key = Depends(verify_api_key)
):
    """Get task by ID với async database operations"""
    try:
        stmt = select(AgentTask).where(AgentTask.id == task_id)
        result = await db.execute(stmt)
        task = result.scalar_one_or_none()
        if task is None:
            raise HTTPException(status_code=404, detail="Task not found")
        return task
    except HTTPException:
        raise
    except Exception as e:
        raise handle_database_error(e, context="get_task_async")


@async_router.put("/tasks/{task_id}", response_model=TaskResponse)
async def update_task_async(
    request: Request,
    task_id: int,
    status: str,
    result: Optional[str] = None,
    db: AsyncSession = Depends(get_async_db),
    api_key = Depends(verify_api_key)
):
    """Update task với async database operations"""
    try:
        from datetime import datetime
        
        stmt = select(AgentTask).where(AgentTask.id == task_id)
        result_query = await db.execute(stmt)
        task = result_query.scalar_one_or_none()
        
        if task is None:
            raise HTTPException(status_code=404, detail="Task not found")
        
        task.status = status
        if result:
            task.result = result
        task.updated_at = datetime.utcnow()
        
        await db.commit()
        await db.refresh(task)
        return task
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise handle_database_error(e, context="update_task_async")


# Async Conversation endpoints
@async_router.post("/conversations", response_model=ConversationResponse)
@limiter_with_api_key.limit(STRICT_RATE_LIMIT)
async def create_conversation_async(
    request: Request,
    conversation: ConversationCreate,
    db: AsyncSession = Depends(get_async_db),
    api_key: str = Depends(verify_api_key)
):
    """
    Tạo conversation mới với AI response từ LLM (async version)
    Sử dụng Celery cho background indexing
    """
    try:
        # Lấy conversation history nếu có session_id
        conversation_history = []
        if conversation.session_id:
            stmt = select(AgentConversation).where(
                AgentConversation.session_id == conversation.session_id
            ).order_by(AgentConversation.created_at)
            result = await db.execute(stmt)
            previous_convs = result.scalars().all()
            
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
        
        # Semantic search để tìm similar conversations (async)
        semantic_context = []
        best_response = None
        suggestions = {}
        semantic_service = None
        
        try:
            from services.semantic_search_service import SemanticSearchService
            semantic_service = SemanticSearchService(db)
            semantic_context = await semantic_service.get_semantic_context(
                user_message=conversation.user_message,
                context_limit=3
            )
        except Exception as e:
            logger.warning(f"Error in semantic search, continuing without context: {e}")
        
        # Phân tích patterns và tìm suggestions (async nếu có)
        try:
            from services.pattern_analysis_service import PatternAnalysisService
            pattern_service = PatternAnalysisService(db)
            # Note: pattern_service có thể cần convert sang async
            suggestions = await run_sync_in_thread(
                pattern_service.get_response_suggestions,
                conversation.user_message,
                use_patterns=True
            )
        except Exception as e:
            logger.warning(f"Error in pattern analysis, continuing without suggestions: {e}")
            suggestions = {}
        
        # Kết hợp semantic search results với pattern suggestions
        if semantic_context:
            suggestions["semantic_matches"] = semantic_context
        
        # Tìm best response từ semantic search
        if semantic_service:
            try:
                best_response = await semantic_service.find_best_response(
                    user_message=conversation.user_message,
                    limit=1,
                    min_similarity=0.7
                )
            except Exception as e:
                logger.warning(f"Error finding best response, continuing: {e}")
        
        # Tạo enhanced system prompt
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
            for i, ctx in enumerate(semantic_context[:2], 1):
                context_text += f"{i}. User: {ctx['user_message'][:100]}...\n"
                context_text += f"   Assistant: {ctx['ai_response'][:150]}...\n"
            system_prompt += context_text
        
        # Nếu có best response với high confidence, tham khảo
        if best_response and best_response.get("confidence") == "high":
            system_prompt += f"\n\nTham khảo response tốt (similarity: {best_response['similarity']:.2f}): {best_response['suggested_response'][:200]}"
        
        # Generate AI response từ LLM (async)
        ai_response = await llm_service.generate_response(
            user_message=conversation.user_message,
            conversation_history=conversation_history if conversation_history else None,
            system_prompt=system_prompt
        )
        
        # Lưu vào database (async)
        db_conversation = AgentConversation(
            user_message=conversation.user_message,
            ai_response=ai_response,
            session_id=conversation.session_id
        )
        db.add(db_conversation)
        await db.commit()
        await db.refresh(db_conversation)
        
        # Index conversation trong background qua Celery (không block response)
        index_conversation_task.delay(
            conversation_id=db_conversation.id,
            user_message=conversation.user_message,
            ai_response=ai_response
        )
        
        return db_conversation
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise handle_error(
            e,
            category=ErrorCategory.LLM,
            severity=ErrorSeverity.ERROR,
            context="create_conversation_async",
            user_message="Không thể tạo conversation. Vui lòng thử lại sau.",
            status_code=500
        )


@async_router.get("/conversations", response_model=List[ConversationResponse])
async def get_conversations_async(
    request: Request,
    session_id: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_async_db),
    api_key = Depends(verify_api_key)
):
    """Get conversations với async database operations"""
    try:
        stmt = select(AgentConversation)
        if session_id:
            stmt = stmt.where(AgentConversation.session_id == session_id)
        stmt = stmt.order_by(AgentConversation.created_at.desc()).offset(skip).limit(limit)
        
        result = await db.execute(stmt)
        conversations = result.scalars().all()
        return conversations
    except Exception as e:
        raise handle_database_error(e, context="get_conversations_async")

