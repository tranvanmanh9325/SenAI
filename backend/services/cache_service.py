"""
Cache Service để quản lý Redis caching
Hỗ trợ cache cho embeddings, LLM responses, và pattern analysis
Backward compatible wrapper around AdvancedCacheService
"""
import os
import json
import hashlib
import logging
from typing import Optional, Any, Dict
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# Try to use advanced cache service if available
try:
    from .advanced_cache_service import get_advanced_cache_service, AdvancedCacheService
    ADVANCED_CACHE_AVAILABLE = True
except ImportError:
    ADVANCED_CACHE_AVAILABLE = False
    logger.warning("Advanced cache service not available, using basic cache")

# Import metrics service nếu có
try:
    from .metrics_service import metrics_service
    METRICS_AVAILABLE = True
except ImportError:
    METRICS_AVAILABLE = False
    metrics_service = None

# Redis configuration
REDIS_ENABLED = os.getenv("REDIS_ENABLED", "false").lower() == "true"

# Auto-configure Redis host nếu được bật
REDIS_AUTO_DETECT = os.getenv("REDIS_AUTO_DETECT", "true").lower() == "true"
if REDIS_ENABLED and REDIS_AUTO_DETECT:
    try:
        from .redis_auto_config import auto_configure_redis
        REDIS_HOST = auto_configure_redis()
    except Exception as e:
        logger.warning(f"Redis auto-configuration failed: {e}, using default")
        REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
else:
    REDIS_HOST = os.getenv("REDIS_HOST", "localhost")

REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_DB = int(os.getenv("REDIS_DB", "0"))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", "").strip()
# Remove comment if present (everything after #)
if '#' in REDIS_PASSWORD:
    REDIS_PASSWORD = REDIS_PASSWORD.split('#')[0].strip()
if not REDIS_PASSWORD:
    REDIS_PASSWORD = None
REDIS_DEFAULT_TTL = int(os.getenv("REDIS_DEFAULT_TTL", "3600"))  # 1 hour default

# Redis client (lazy initialization)
_redis_client = None

def get_redis_client():
    """Get Redis client (lazy initialization)"""
    global _redis_client
    
    if not REDIS_ENABLED:
        return None
    
    if _redis_client is None:
        try:
            import redis
            # Only set password if it's not empty
            # Cấu hình timeout từ environment variables
            redis_connect_timeout = int(os.getenv("REDIS_CONNECT_TIMEOUT", "10"))  # Default 10 seconds
            redis_socket_timeout = int(os.getenv("REDIS_SOCKET_TIMEOUT", "10"))  # Default 10 seconds
            
            redis_kwargs = {
                'host': REDIS_HOST,
                'port': REDIS_PORT,
                'db': REDIS_DB,
                'decode_responses': True,
                'socket_connect_timeout': redis_connect_timeout,
                'socket_timeout': redis_socket_timeout,
                'socket_keepalive': True,  # Giữ connection alive
                'health_check_interval': 30,  # Check connection health mỗi 30 giây
            }
            if REDIS_PASSWORD and REDIS_PASSWORD.strip():
                redis_kwargs['password'] = REDIS_PASSWORD.strip()
            
            _redis_client = redis.Redis(**redis_kwargs)
            
            # Test connection với better error handling
            try:
                _redis_client.ping()
                logger.info(f"Redis connected: {REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}")
            except redis.ConnectionError as e:
                logger.warning(f"Redis ping failed: {e}")
                _redis_client = None
            except redis.AuthenticationError as e:
                logger.warning(f"Redis authentication failed. Please check REDIS_PASSWORD.")
                _redis_client = None
        except ImportError:
            logger.warning("redis package not installed. Install with: pip install redis")
            return None
        except Exception as e:
            logger.warning(f"Redis connection failed: {e}. Caching will be disabled.")
            return None
    
    return _redis_client

class CacheService:
    """Service để quản lý caching - Backward compatible wrapper"""
    
    def __init__(self, db_session=None):
        # Use advanced cache service if available
        if ADVANCED_CACHE_AVAILABLE:
            try:
                self.advanced_cache = get_advanced_cache_service(db_session=db_session)
                self.enabled = True
                self._use_advanced = True
                logger.info("Using Advanced Multi-Level Cache Service")
                return
            except Exception as e:
                logger.warning(f"Failed to initialize advanced cache, falling back to basic: {e}")
        
        # Fallback to basic Redis cache
        self._use_advanced = False
        self.redis_client = get_redis_client()
        self.enabled = REDIS_ENABLED and self.redis_client is not None
        
        if not self.enabled:
            logger.info("Caching is disabled (REDIS_ENABLED=false or Redis not available)")
    
    def _generate_key(self, prefix: str, *args, **kwargs) -> str:
        """Generate cache key từ prefix và arguments"""
        # Combine all arguments into a string
        key_parts = [prefix]
        
        # Add positional arguments
        for arg in args:
            if isinstance(arg, (dict, list)):
                key_parts.append(json.dumps(arg, sort_keys=True))
            else:
                key_parts.append(str(arg))
        
        # Add keyword arguments
        if kwargs:
            sorted_kwargs = sorted(kwargs.items())
            key_parts.append(json.dumps(sorted_kwargs, sort_keys=True))
        
        # Create hash for long keys
        key_string = ":".join(key_parts)
        if len(key_string) > 200:  # Redis key length limit
            key_hash = hashlib.md5(key_string.encode()).hexdigest()
            return f"{prefix}:{key_hash}"
        
        return key_string
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        if not self.enabled:
            return None
        
        if self._use_advanced:
            return self.advanced_cache.get(key)
        
        try:
            value = self.redis_client.get(key)
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            logger.warning(f"Cache get error for key {key}: {e}")
            return None
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set value in cache with optional TTL"""
        if not self.enabled:
            return False
        
        if self._use_advanced:
            return self.advanced_cache.set(key, value, ttl)
        
        try:
            ttl = ttl or REDIS_DEFAULT_TTL
            value_json = json.dumps(value)
            self.redis_client.setex(key, ttl, value_json)
            return True
        except Exception as e:
            logger.warning(f"Cache set error for key {key}: {e}")
            return False
    
    def delete(self, key: str) -> bool:
        """Delete key from cache"""
        if not self.enabled:
            return False
        
        if self._use_advanced:
            return self.advanced_cache.delete(key)
        
        try:
            self.redis_client.delete(key)
            return True
        except Exception as e:
            logger.warning(f"Cache delete error for key {key}: {e}")
            return False
    
    def get_embedding_key(self, text: str) -> str:
        """Generate cache key for embedding"""
        return self._generate_key("embedding", text)
    
    def get_llm_response_key(self, user_message: str, conversation_history: Optional[list] = None, 
                             system_prompt: Optional[str] = None, temperature: float = 0.7) -> str:
        """Generate cache key for LLM response"""
        return self._generate_key("llm_response", user_message, conversation_history, 
                                  system_prompt, temperature)
    
    def get_pattern_analysis_key(self, session_id: str, limit: int = 10) -> str:
        """Generate cache key for pattern analysis"""
        return self._generate_key("pattern_analysis", session_id, limit)
    
    def cache_embedding(self, text: str, embedding: list, ttl: Optional[int] = None) -> bool:
        """Cache embedding result"""
        if self._use_advanced:
            return self.advanced_cache.cache_embedding(text, embedding, ttl)
        key = self.get_embedding_key(text)
        return self.set(key, embedding, ttl)
    
    def get_cached_embedding(self, text: str) -> Optional[list]:
        """Get cached embedding"""
        if self._use_advanced:
            return self.advanced_cache.get_cached_embedding(text)
        key = self.get_embedding_key(text)
        return self.get(key)
    
    def cache_llm_response(self, user_message: str, response: str, 
                          conversation_history: Optional[list] = None,
                          system_prompt: Optional[str] = None,
                          temperature: float = 0.7,
                          ttl: Optional[int] = None) -> bool:
        """Cache LLM response"""
        if self._use_advanced:
            return self.advanced_cache.cache_llm_response(
                user_message, response, conversation_history, system_prompt, temperature, ttl
            )
        key = self.get_llm_response_key(user_message, conversation_history, system_prompt, temperature)
        return self.set(key, response, ttl)
    
    def get_cached_llm_response(self, user_message: str, 
                               conversation_history: Optional[list] = None,
                               system_prompt: Optional[str] = None,
                               temperature: float = 0.7) -> Optional[str]:
        """Get cached LLM response"""
        if self._use_advanced:
            return self.advanced_cache.get_cached_llm_response(
                user_message, conversation_history, system_prompt, temperature
            )
        key = self.get_llm_response_key(user_message, conversation_history, system_prompt, temperature)
        return self.get(key)
    
    def clear_llm_cache(self, user_message: str,
                       conversation_history: Optional[list] = None,
                       system_prompt: Optional[str] = None,
                       temperature: float = 0.7) -> bool:
        """Clear cached LLM response for specific key"""
        key = self.get_llm_response_key(user_message, conversation_history, system_prompt, temperature)
        return self.delete(key)
    
    def cache_pattern_analysis(self, session_id: str, analysis: Dict[str, Any], 
                              limit: int = 10, ttl: Optional[int] = None) -> bool:
        """Cache pattern analysis result"""
        if self._use_advanced:
            return self.advanced_cache.cache_pattern_analysis(session_id, analysis, limit, ttl)
        key = self.get_pattern_analysis_key(session_id, limit)
        return self.set(key, analysis, ttl)
    
    def get_cached_pattern_analysis(self, session_id: str, limit: int = 10) -> Optional[Dict[str, Any]]:
        """Get cached pattern analysis"""
        if self._use_advanced:
            return self.advanced_cache.get_cached_pattern_analysis(session_id, limit)
        key = self.get_pattern_analysis_key(session_id, limit)
        return self.get(key)
    
    def clear_cache(self, pattern: str = "*") -> int:
        """Clear cache by pattern (use with caution)"""
        if not self.enabled:
            return 0
        
        if self._use_advanced:
            return self.advanced_cache.invalidate_pattern(pattern)
        
        try:
            keys = self.redis_client.keys(pattern)
            if keys:
                return self.redis_client.delete(*keys)
            return 0
        except Exception as e:
            logger.warning(f"Cache clear error for pattern {pattern}: {e}")
            return 0
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        if self._use_advanced:
            return self.advanced_cache.get_stats()
        
        # Basic stats for fallback
        return {
            "enabled": self.enabled,
            "backend": "redis" if self.enabled else "disabled"
        }

# Global cache service instance (will be initialized with db_session when available)
cache_service = CacheService()