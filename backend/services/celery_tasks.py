"""
Celery Tasks for Background Processing
Các background tasks chạy qua Celery worker
"""
import logging
from typing import Dict, Any, List, Optional
from celery import Task
from services.celery_config import celery_app
from services.async_database_config import get_async_database_config, AsyncDatabaseConfig
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
import asyncio

logger = logging.getLogger(__name__)

# Import models
from config.models import (
    AgentConversation, ConversationEmbedding, CacheEntry
)


class DatabaseTask(Task):
    """Base task class với database session management"""
    _db_config: Optional[AsyncDatabaseConfig] = None
    _async_session_factory = None
    
    def __init__(self):
        super().__init__()
        if self._db_config is None:
            self._db_config = get_async_database_config()
            engine = self._db_config.create_async_engine()
            self._async_session_factory = self._db_config.create_async_session_factory(engine)
    
    async def get_db_session(self) -> AsyncSession:
        """Lấy async database session"""
        if self._async_session_factory is None:
            self._db_config = get_async_database_config()
            engine = self._db_config.create_async_engine()
            self._async_session_factory = self._db_config.create_async_session_factory(engine)
        return self._async_session_factory()


@celery_app.task(base=DatabaseTask, bind=True, name='services.celery_tasks.index_conversation')
def index_conversation_task(self, conversation_id: int, user_message: str, ai_response: str):
    """
    Background task để index conversation (tạo embeddings)
    Chạy qua Celery worker
    """
    async def _index_conversation():
        try:
            db = await self.get_db_session()
            try:
                from services.semantic_search_service import SemanticSearchService
                semantic_service = SemanticSearchService(db)
                indexing_result = await semantic_service.index_conversation(
                    conversation_id=conversation_id,
                    user_message=user_message,
                    ai_response=ai_response
                )
                if not indexing_result.get("success"):
                    logger.warning(f"Failed to index conversation {conversation_id}: {indexing_result.get('error')}")
                return indexing_result
            finally:
                await db.close()
        except Exception as e:
            logger.error(f"Error indexing conversation {conversation_id} in background: {e}")
            raise
    
    # Run async function in event loop
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If loop is already running, use nest_asyncio
            try:
                import nest_asyncio
                nest_asyncio.apply()
                return loop.run_until_complete(_index_conversation())
            except ImportError:
                # Fallback: create new event loop in thread
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, _index_conversation())
                    return future.result()
        else:
            return asyncio.run(_index_conversation())
    except RuntimeError:
        # No event loop, create new one
        return asyncio.run(_index_conversation())


@celery_app.task(base=DatabaseTask, bind=True, name='services.celery_tasks.batch_process')
def batch_process_task(self, task_type: str, data: List[Dict[str, Any]]):
    """
    Batch processing task cho bulk operations
    """
    async def _batch_process():
        try:
            db = await self.get_db_session()
            try:
                if task_type == "bulk_insert_conversations":
                    from config.models import AgentConversation
                    from datetime import datetime
                    
                    conversations = []
                    for item in data:
                        conv = AgentConversation(
                            user_message=item.get("user_message"),
                            ai_response=item.get("ai_response"),
                            session_id=item.get("session_id"),
                            created_at=datetime.utcnow()
                        )
                        conversations.append(conv)
                    
                    db.add_all(conversations)
                    await db.commit()
                    
                    return {
                        "success": True,
                        "count": len(conversations),
                        "task_type": task_type
                    }
                
                elif task_type == "bulk_update_cache":
                    from config.models import CacheEntry
                    from datetime import datetime, timedelta
                    import json
                    
                    updated = 0
                    for item in data:
                        cache_key = item.get("cache_key")
                        cache_value = item.get("cache_value")
                        ttl = item.get("ttl", 3600)
                        
                        result = await db.execute(
                            select(CacheEntry).where(CacheEntry.cache_key == cache_key)
                        )
                        cache_entry = result.scalar_one_or_none()
                        
                        if cache_entry:
                            cache_entry.cache_value = json.dumps(cache_value) if isinstance(cache_value, (dict, list)) else str(cache_value)
                            cache_entry.expires_at = datetime.utcnow() + timedelta(seconds=ttl)
                            cache_entry.last_accessed = datetime.utcnow()
                            updated += 1
                    
                    await db.commit()
                    
                    return {
                        "success": True,
                        "updated": updated,
                        "task_type": task_type
                    }
                
                else:
                    return {
                        "success": False,
                        "error": f"Unknown task type: {task_type}"
                    }
            finally:
                await db.close()
        except Exception as e:
            logger.error(f"Error in batch process task {task_type}: {e}")
            raise
    
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            try:
                import nest_asyncio
                nest_asyncio.apply()
                return loop.run_until_complete(_batch_process())
            except ImportError:
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, _batch_process())
                    return future.result()
        else:
            return asyncio.run(_batch_process())
    except RuntimeError:
        return asyncio.run(_batch_process())


@celery_app.task(name='services.celery_tasks.cleanup_expired_cache')
def cleanup_expired_cache_task():
    """
    Cleanup expired cache entries từ database
    """
    async def _cleanup():
        try:
            db_config = get_async_database_config()
            engine = db_config.create_async_engine()
            async_session_factory = db_config.create_async_session_factory(engine)
            
            async with async_session_factory() as db:
                from config.models import CacheEntry
                from datetime import datetime
                from sqlalchemy import delete
                
                # Delete expired cache entries
                result = await db.execute(
                    delete(CacheEntry).where(CacheEntry.expires_at < datetime.utcnow())
                )
                await db.commit()
                
                deleted_count = result.rowcount
                logger.info(f"Cleaned up {deleted_count} expired cache entries")
                
                return {
                    "success": True,
                    "deleted_count": deleted_count
                }
        except Exception as e:
            logger.error(f"Error cleaning up expired cache: {e}")
            raise
        finally:
            await engine.dispose()
    
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            try:
                import nest_asyncio
                nest_asyncio.apply()
                return loop.run_until_complete(_cleanup())
            except ImportError:
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, _cleanup())
                    return future.result()
        else:
            return asyncio.run(_cleanup())
    except RuntimeError:
        return asyncio.run(_cleanup())

