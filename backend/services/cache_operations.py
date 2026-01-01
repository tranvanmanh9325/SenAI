"""
Cache operations for L2 (Redis) and L3 (Database) levels.
This module contains operations for Redis cache, database cache, cache warming,
and convenience methods for specific cache types.
"""
import json
import logging
import time
from typing import Optional, Any, Dict, List
from datetime import datetime, timedelta

from .cache_components import CacheLevel

logger = logging.getLogger(__name__)


class CacheOperations:
    """Operations for L2 (Redis) and L3 (Database) cache levels"""
    
    @staticmethod
    def set_to_l2(redis_client, key: str, value: Any, ttl: int) -> bool:
        """Set value in L2 (Redis)"""
        try:
            value_json = json.dumps(value)
            redis_client.setex(key, ttl, value_json)
            return True
        except Exception as e:
            logger.warning(f"L2 cache set error for key {key}: {e}")
            return False
    
    @staticmethod
    def get_from_l2(redis_client, key: str) -> Optional[Any]:
        """Get value from L2 (Redis)"""
        try:
            cached_data = redis_client.get(key)
            if cached_data:
                return json.loads(cached_data)
            return None
        except Exception as e:
            logger.warning(f"L2 cache get error for key {key}: {e}")
            return None
    
    @staticmethod
    def delete_from_l2(redis_client, key: str) -> bool:
        """Delete key from L2 (Redis)"""
        try:
            redis_client.delete(key)
            return True
        except Exception as e:
            logger.warning(f"L2 cache delete error for key {key}: {e}")
            return False
    
    @staticmethod
    def invalidate_pattern_l2(redis_client, pattern: str) -> int:
        """Invalidate cache entries matching pattern in L2"""
        try:
            keys = redis_client.keys(f"*{pattern}*")
            if keys:
                deleted = redis_client.delete(*keys)
                return deleted
            return 0
        except Exception as e:
            logger.warning(f"L2 cache invalidate_pattern error: {e}")
            return 0
    
    @staticmethod
    def set_to_l3(db_session, key: str, value: Any, ttl: int, cache_type: str) -> bool:
        """Set value in L3 (Database)"""
        try:
            from models import CacheEntry as CacheEntryModel
            
            expires_at = datetime.now() + timedelta(seconds=ttl)
            value_json = json.dumps(value)
            
            # Check if entry exists
            existing = db_session.query(CacheEntryModel).filter(
                CacheEntryModel.cache_key == key
            ).first()
            
            if existing:
                existing.cache_value = value_json
                existing.expires_at = expires_at
                existing.access_count += 1
                existing.last_accessed = datetime.now()
            else:
                new_entry = CacheEntryModel(
                    cache_key=key,
                    cache_value=value_json,
                    cache_type=cache_type,
                    expires_at=expires_at,
                    access_count=1,
                    last_accessed=datetime.now()
                )
                db_session.add(new_entry)
            
            db_session.commit()
            return True
        except ImportError:
            logger.warning("CacheEntry model not found. L3 cache disabled. Run migration to enable.")
            return False
        except Exception as e:
            logger.error(f"L3 cache set error for key {key}: {e}")
            if db_session:
                db_session.rollback()
            return False
    
    @staticmethod
    def get_from_l3(db_session, key: str) -> Optional[Any]:
        """Get value from L3 (Database)"""
        try:
            from models import CacheEntry as CacheEntryModel
            
            entry = db_session.query(CacheEntryModel).filter(
                CacheEntryModel.cache_key == key,
                CacheEntryModel.expires_at > datetime.now()
            ).first()
            
            if entry:
                # Update access stats
                entry.access_count += 1
                entry.last_accessed = datetime.now()
                db_session.commit()
                
                return json.loads(entry.cache_value)
            
            return None
        except ImportError:
            logger.warning("CacheEntry model not found. L3 cache disabled. Run migration to enable.")
            return None
        except Exception as e:
            logger.error(f"L3 cache get error for key {key}: {e}")
            return None
    
    @staticmethod
    def delete_from_l3(db_session, key: str) -> bool:
        """Delete key from L3 (Database)"""
        try:
            from models import CacheEntry as CacheEntryModel
            db_session.query(CacheEntryModel).filter(
                CacheEntryModel.cache_key == key
            ).delete()
            db_session.commit()
            return True
        except ImportError:
            logger.warning("CacheEntry model not found. L3 cache disabled.")
            return False
        except Exception as e:
            logger.error(f"L3 cache delete error for key {key}: {e}")
            return False
    
    @staticmethod
    def invalidate_pattern_l3(db_session, pattern: str) -> int:
        """Invalidate cache entries matching pattern in L3"""
        try:
            from models import CacheEntry as CacheEntryModel
            
            deleted = db_session.query(CacheEntryModel).filter(
                CacheEntryModel.cache_key.like(f"%{pattern}%")
            ).delete(synchronize_session=False)
            db_session.commit()
            return deleted
        except ImportError:
            logger.warning("CacheEntry model not found. L3 cache disabled.")
            return 0
        except Exception as e:
            logger.error(f"L3 cache invalidate_pattern error: {e}")
            return 0
    
    @staticmethod
    def warm_cache(l1_cache, l2_enabled, redis_client, db_session, l3_enabled,
                   l1_default_ttl: int = 300, l2_default_ttl: int = 3600,
                   warming_top_n: int = 100) -> int:
        """Warm cache with frequently accessed items from L3"""
        if not l3_enabled:
            return 0
        
        try:
            from models import CacheEntry as CacheEntryModel
            
            # Get top N frequently accessed items from L3
            top_items = db_session.query(CacheEntryModel).filter(
                CacheEntryModel.expires_at > datetime.now()
            ).order_by(
                CacheEntryModel.access_count.desc()
            ).limit(warming_top_n).all()
            
            warmed_count = 0
            for item in top_items:
                try:
                    value = json.loads(item.cache_value)
                    # Promote to L1 and L2
                    l1_cache.set(item.cache_key, value, l1_default_ttl, item.cache_type)
                    if l2_enabled:
                        CacheOperations.set_to_l2(redis_client, item.cache_key, value, l2_default_ttl)
                    
                    warmed_count += 1
                except Exception as e:
                    logger.warning(f"Error warming cache for key {item.cache_key}: {e}")
            
            if warmed_count > 0:
                logger.info(f"Cache warmed: {warmed_count} items promoted to L1/L2")
            
            return warmed_count
        
        except ImportError:
            logger.warning("CacheEntry model not found. Cache warming disabled.")
            return 0
        except Exception as e:
            logger.error(f"Cache warming error: {e}")
            return 0


class CacheConvenienceMethods:
    """Convenience methods for specific cache types"""
    
    def __init__(self, cache_service):
        """Initialize with reference to cache service"""
        self.cache_service = cache_service
    
    def get_embedding_key(self, text: str) -> str:
        """Generate cache key for embedding"""
        return self.cache_service._generate_key("embedding", text)
    
    def get_llm_response_key(self, user_message: str, conversation_history: Optional[list] = None,
                             system_prompt: Optional[str] = None, temperature: float = 0.7) -> str:
        """Generate cache key for LLM response"""
        return self.cache_service._generate_key("llm_response", user_message, conversation_history,
                                                 system_prompt, temperature)
    
    def get_pattern_analysis_key(self, session_id: str, limit: int = 10) -> str:
        """Generate cache key for pattern analysis"""
        return self.cache_service._generate_key("pattern_analysis", session_id, limit)
    
    def cache_embedding(self, text: str, embedding: list, ttl: Optional[int] = None) -> bool:
        """Cache embedding result"""
        key = self.get_embedding_key(text)
        return self.cache_service.set(key, embedding, ttl, cache_type="embedding")
    
    def get_cached_embedding(self, text: str) -> Optional[list]:
        """Get cached embedding"""
        key = self.get_embedding_key(text)
        return self.cache_service.get(key, cache_type="embedding")
    
    def cache_llm_response(self, user_message: str, response: str,
                          conversation_history: Optional[list] = None,
                          system_prompt: Optional[str] = None,
                          temperature: float = 0.7,
                          ttl: Optional[int] = None) -> bool:
        """Cache LLM response"""
        key = self.get_llm_response_key(user_message, conversation_history, system_prompt, temperature)
        return self.cache_service.set(key, response, ttl, cache_type="llm")
    
    def get_cached_llm_response(self, user_message: str,
                                 conversation_history: Optional[list] = None,
                                 system_prompt: Optional[str] = None,
                                 temperature: float = 0.7) -> Optional[str]:
        """Get cached LLM response"""
        key = self.get_llm_response_key(user_message, conversation_history, system_prompt, temperature)
        return self.cache_service.get(key, cache_type="llm")
    
    def cache_pattern_analysis(self, session_id: str, analysis: Dict[str, Any],
                                limit: int = 10, ttl: Optional[int] = None) -> bool:
        """Cache pattern analysis result"""
        key = self.get_pattern_analysis_key(session_id, limit)
        return self.cache_service.set(key, analysis, ttl, cache_type="pattern_analysis")
    
    def get_cached_pattern_analysis(self, session_id: str, limit: int = 10) -> Optional[Dict[str, Any]]:
        """Get cached pattern analysis"""
        key = self.get_pattern_analysis_key(session_id, limit)
        return self.cache_service.get(key, cache_type="pattern_analysis")