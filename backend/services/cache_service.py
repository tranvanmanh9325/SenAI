"""
Cache Service để quản lý Redis caching
Hỗ trợ cache cho embeddings, LLM responses, và pattern analysis
"""
import os
import json
import hashlib
import logging
from typing import Optional, Any, Dict
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# Import metrics service nếu có
try:
    from .metrics_service import metrics_service
    METRICS_AVAILABLE = True
except ImportError:
    METRICS_AVAILABLE = False
    metrics_service = None

# Redis configuration
REDIS_ENABLED = os.getenv("REDIS_ENABLED", "false").lower() == "true"
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
            redis_kwargs = {
                'host': REDIS_HOST,
                'port': REDIS_PORT,
                'db': REDIS_DB,
                'decode_responses': True,
                'socket_connect_timeout': 5,
                'socket_timeout': 5
            }
            if REDIS_PASSWORD and REDIS_PASSWORD.strip():
                redis_kwargs['password'] = REDIS_PASSWORD.strip()
            
            _redis_client = redis.Redis(**redis_kwargs)
            # Test connection
            _redis_client.ping()
            logger.info(f"Redis connected: {REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}")
        except ImportError:
            logger.warning("redis package not installed. Install with: pip install redis")
            return None
        except Exception as e:
            logger.warning(f"Redis connection failed: {e}. Caching will be disabled.")
            return None
    
    return _redis_client

class CacheService:
    """Service để quản lý caching"""
    
    def __init__(self):
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
        key = self.get_embedding_key(text)
        return self.set(key, embedding, ttl)
    
    def get_cached_embedding(self, text: str) -> Optional[list]:
        """Get cached embedding"""
        key = self.get_embedding_key(text)
        return self.get(key)
    
    def cache_llm_response(self, user_message: str, response: str, 
                          conversation_history: Optional[list] = None,
                          system_prompt: Optional[str] = None,
                          temperature: float = 0.7,
                          ttl: Optional[int] = None) -> bool:
        """Cache LLM response"""
        key = self.get_llm_response_key(user_message, conversation_history, system_prompt, temperature)
        return self.set(key, response, ttl)
    
    def get_cached_llm_response(self, user_message: str, 
                               conversation_history: Optional[list] = None,
                               system_prompt: Optional[str] = None,
                               temperature: float = 0.7) -> Optional[str]:
        """Get cached LLM response"""
        key = self.get_llm_response_key(user_message, conversation_history, system_prompt, temperature)
        return self.get(key)
    
    def cache_pattern_analysis(self, session_id: str, analysis: Dict[str, Any], 
                              limit: int = 10, ttl: Optional[int] = None) -> bool:
        """Cache pattern analysis result"""
        key = self.get_pattern_analysis_key(session_id, limit)
        return self.set(key, analysis, ttl)
    
    def get_cached_pattern_analysis(self, session_id: str, limit: int = 10) -> Optional[Dict[str, Any]]:
        """Get cached pattern analysis"""
        key = self.get_pattern_analysis_key(session_id, limit)
        return self.get(key)
    
    def clear_cache(self, pattern: str = "*") -> int:
        """Clear cache by pattern (use with caution)"""
        if not self.enabled:
            return 0
        
        try:
            keys = self.redis_client.keys(pattern)
            if keys:
                return self.redis_client.delete(*keys)
            return 0
        except Exception as e:
            logger.warning(f"Cache clear error for pattern {pattern}: {e}")
            return 0

# Global cache service instance
cache_service = CacheService()