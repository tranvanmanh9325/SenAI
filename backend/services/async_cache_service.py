"""
Async Cache Service Wrapper
Async wrapper cho AdvancedCacheService để hỗ trợ async operations
"""
import logging
import asyncio
from typing import Optional, Any, Dict, List
from services.advanced_cache_service import AdvancedCacheService, CacheLevel

logger = logging.getLogger(__name__)


class AsyncCacheService:
    """Async wrapper cho AdvancedCacheService"""
    
    def __init__(self, db_session=None):
        self.cache_service = AdvancedCacheService(db_session=db_session)
    
    async def get(self, key: str, cache_type: str = "generic") -> Optional[Any]:
        """Async get từ cache"""
        # Run sync operation in thread pool
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self.cache_service.get,
            key,
            cache_type
        )
    
    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
        cache_type: str = "generic",
        levels: List[CacheLevel] = None
    ) -> bool:
        """Async set vào cache"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self.cache_service.set,
            key,
            value,
            ttl,
            cache_type,
            levels
        )
    
    async def delete(self, key: str, levels: List[CacheLevel] = None) -> bool:
        """Async delete từ cache"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self.cache_service.delete,
            key,
            levels
        )
    
    async def invalidate_pattern(
        self,
        pattern: str,
        levels: List[CacheLevel] = None
    ) -> int:
        """Async invalidate pattern"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self.cache_service.invalidate_pattern,
            pattern,
            levels
        )
    
    async def get_stats(self) -> Dict[str, Any]:
        """Async get cache statistics"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self.cache_service.get_stats
        )
    
    # Convenience methods
    async def get_cached_embedding(self, text: str) -> Optional[list]:
        """Async get cached embedding"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self.cache_service.get_cached_embedding,
            text
        )
    
    async def cache_embedding(
        self,
        text: str,
        embedding: list,
        ttl: Optional[int] = None
    ) -> bool:
        """Async cache embedding"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self.cache_service.cache_embedding,
            text,
            embedding,
            ttl
        )
    
    async def get_cached_llm_response(
        self,
        user_message: str,
        conversation_history: Optional[list] = None,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7
    ) -> Optional[str]:
        """Async get cached LLM response"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self.cache_service.get_cached_llm_response,
            user_message,
            conversation_history,
            system_prompt,
            temperature
        )
    
    async def cache_llm_response(
        self,
        user_message: str,
        response: str,
        conversation_history: Optional[list] = None,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        ttl: Optional[int] = None
    ) -> bool:
        """Async cache LLM response"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self.cache_service.cache_llm_response,
            user_message,
            response,
            conversation_history,
            system_prompt,
            temperature,
            ttl
        )


# Global instance
_async_cache_service = None


def get_async_cache_service(db_session=None) -> AsyncCacheService:
    """Get or create async cache service instance"""
    global _async_cache_service
    
    if _async_cache_service is None:
        _async_cache_service = AsyncCacheService(db_session=db_session)
    elif db_session is not None and _async_cache_service.cache_service.db_session is None:
        _async_cache_service.cache_service.db_session = db_session
        _async_cache_service.cache_service.l3_enabled = True
    
    return _async_cache_service


