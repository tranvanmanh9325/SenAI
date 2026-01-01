"""
Database Query Caching Service
Cung cấp caching layer cho database queries để giảm load và tăng performance
"""
import hashlib
import json
import logging
from typing import Any, Optional, Callable, Dict
from datetime import datetime, timedelta
from functools import wraps
import os

logger = logging.getLogger(__name__)

# Try to import Redis for caching
try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    logger.warning("Redis not available. Query caching will use in-memory cache only.")

# In-memory cache fallback
_memory_cache: Dict[str, Dict[str, Any]] = {}
_cache_stats = {
    "hits": 0,
    "misses": 0,
    "sets": 0,
    "evictions": 0
}


class QueryCacheService:
    """Service để cache database query results"""
    
    def __init__(self):
        self.redis_client = None
        self.use_redis = False
        self.default_ttl = int(os.getenv("QUERY_CACHE_TTL", "300"))  # 5 minutes default
        
        # Redis configuration
        redis_host = os.getenv("REDIS_HOST", "localhost")
        redis_port = int(os.getenv("REDIS_PORT", "6379"))
        redis_db = int(os.getenv("REDIS_DB", "0"))
        redis_password = os.getenv("REDIS_PASSWORD", None)
        
        # Chỉ kết nối Redis nếu được cấu hình rõ ràng
        redis_enabled = os.getenv("REDIS_ENABLED", "false").lower() == "true"
        
        if REDIS_AVAILABLE and redis_enabled:
            try:
                # Chỉ thêm password vào connection nếu được cấu hình
                redis_kwargs = {
                    "host": redis_host,
                    "port": redis_port,
                    "db": redis_db,
                    "decode_responses": True,
                    "socket_connect_timeout": 5,
                    "socket_timeout": 5
                }
                
                # Chỉ thêm password nếu được cấu hình và không rỗng
                if redis_password and redis_password.strip():
                    redis_kwargs["password"] = redis_password
                
                self.redis_client = redis.Redis(**redis_kwargs)
                # Test connection
                self.redis_client.ping()
                self.use_redis = True
                logger.info(f"✅ Redis cache connected: {redis_host}:{redis_port}")
            except redis.AuthenticationError as e:
                logger.warning(f"⚠️  Redis authentication failed, sử dụng in-memory cache: {e}")
                self.use_redis = False
            except Exception as e:
                logger.warning(f"⚠️  Redis không khả dụng, sử dụng in-memory cache: {e}")
                self.use_redis = False
        elif REDIS_AVAILABLE and not redis_enabled:
            logger.debug("Redis available but disabled (REDIS_ENABLED=false), using in-memory cache")
            self.use_redis = False
        else:
            logger.info("ℹ️  Redis không được cài đặt, sử dụng in-memory cache")
    
    def _generate_cache_key(self, query: str, params: Optional[Dict[str, Any]] = None) -> str:
        """Generate cache key từ query và parameters"""
        # Normalize query (remove extra whitespace)
        normalized_query = " ".join(query.split())
        
        # Include params in key
        if params:
            params_str = json.dumps(params, sort_keys=True)
            key_data = f"{normalized_query}:{params_str}"
        else:
            key_data = normalized_query
        
        # Hash để tạo key ngắn gọn
        key_hash = hashlib.sha256(key_data.encode()).hexdigest()
        return f"query_cache:{key_hash}"
    
    def get(self, query: str, params: Optional[Dict[str, Any]] = None) -> Optional[Any]:
        """
        Lấy kết quả từ cache
        
        Args:
            query: SQL query string
            params: Query parameters
        
        Returns:
            Cached result hoặc None nếu không có trong cache
        """
        cache_key = self._generate_cache_key(query, params)
        
        try:
            if self.use_redis and self.redis_client:
                # Try Redis first
                cached_data = self.redis_client.get(cache_key)
                if cached_data:
                    _cache_stats["hits"] += 1
                    return json.loads(cached_data)
                else:
                    _cache_stats["misses"] += 1
                    return None
            else:
                # Use in-memory cache
                if cache_key in _memory_cache:
                    cache_entry = _memory_cache[cache_key]
                    # Check expiration
                    if datetime.now() < cache_entry["expires_at"]:
                        _cache_stats["hits"] += 1
                        return cache_entry["data"]
                    else:
                        # Expired, remove it
                        del _memory_cache[cache_key]
                        _cache_stats["evictions"] += 1
                
                _cache_stats["misses"] += 1
                return None
        
        except Exception as e:
            logger.error(f"Error getting from cache: {e}")
            _cache_stats["misses"] += 1
            return None
    
    def set(self, query: str, result: Any, ttl: Optional[int] = None,
            params: Optional[Dict[str, Any]] = None) -> bool:
        """
        Lưu kết quả vào cache
        
        Args:
            query: SQL query string
            result: Query result to cache
            ttl: Time to live in seconds (None = use default)
            params: Query parameters
        
        Returns:
            True nếu thành công, False nếu có lỗi
        """
        cache_key = self._generate_cache_key(query, params)
        ttl = ttl or self.default_ttl
        
        try:
            if self.use_redis and self.redis_client:
                # Store in Redis
                serialized = json.dumps(result, default=str)
                self.redis_client.setex(cache_key, ttl, serialized)
                _cache_stats["sets"] += 1
                return True
            else:
                # Store in memory
                expires_at = datetime.now() + timedelta(seconds=ttl)
                _memory_cache[cache_key] = {
                    "data": result,
                    "expires_at": expires_at,
                    "created_at": datetime.now()
                }
                _cache_stats["sets"] += 1
                
                # Cleanup old entries nếu cache quá lớn (limit 1000 entries)
                if len(_memory_cache) > 1000:
                    # Remove oldest 100 entries
                    sorted_entries = sorted(
                        _memory_cache.items(),
                        key=lambda x: x[1]["created_at"]
                    )
                    for key, _ in sorted_entries[:100]:
                        del _memory_cache[key]
                        _cache_stats["evictions"] += 1
                
                return True
        
        except Exception as e:
            logger.error(f"Error setting cache: {e}")
            return False
    
    def invalidate(self, pattern: Optional[str] = None) -> int:
        """
        Invalidate cache entries
        
        Args:
            pattern: Pattern để match keys (None = clear all)
        
        Returns:
            Số lượng entries đã xóa
        """
        count = 0
        
        try:
            if self.use_redis and self.redis_client:
                if pattern:
                    # Find keys matching pattern
                    keys = self.redis_client.keys(f"query_cache:{pattern}*")
                    if keys:
                        count = self.redis_client.delete(*keys)
                else:
                    # Clear all query cache keys
                    keys = self.redis_client.keys("query_cache:*")
                    if keys:
                        count = self.redis_client.delete(*keys)
            else:
                # In-memory cache
                if pattern:
                    keys_to_delete = [
                        key for key in _memory_cache.keys()
                        if pattern in key
                    ]
                    for key in keys_to_delete:
                        del _memory_cache[key]
                        count += 1
                else:
                    count = len(_memory_cache)
                    _memory_cache.clear()
            
            logger.info(f"Invalidated {count} cache entries")
            return count
        
        except Exception as e:
            logger.error(f"Error invalidating cache: {e}")
            return 0
    
    def get_stats(self) -> Dict[str, Any]:
        """Lấy thống kê về cache"""
        stats = {
            "hits": _cache_stats["hits"],
            "misses": _cache_stats["misses"],
            "sets": _cache_stats["sets"],
            "evictions": _cache_stats["evictions"],
            "hit_rate": 0.0,
            "backend": "redis" if self.use_redis else "memory"
        }
        
        total_requests = stats["hits"] + stats["misses"]
        if total_requests > 0:
            stats["hit_rate"] = stats["hits"] / total_requests
        
        if not self.use_redis:
            stats["memory_entries"] = len(_memory_cache)
        
        return stats


# Singleton instance
_query_cache_service = None


def get_query_cache_service() -> QueryCacheService:
    """Lấy singleton instance của QueryCacheService"""
    global _query_cache_service
    if _query_cache_service is None:
        _query_cache_service = QueryCacheService()
    return _query_cache_service


def cached_query(ttl: Optional[int] = None, key_prefix: Optional[str] = None):
    """
    Decorator để cache function results
    
    Usage:
        @cached_query(ttl=300)
        def get_conversations(session_id: str):
            # ... query database ...
            return results
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            cache_service = get_query_cache_service()
            
            # Generate cache key từ function name và arguments
            key_data = {
                "func": func.__name__,
                "args": str(args),
                "kwargs": json.dumps(kwargs, sort_keys=True, default=str)
            }
            if key_prefix:
                key_data["prefix"] = key_prefix
            
            cache_key = f"func_cache:{hashlib.sha256(json.dumps(key_data, sort_keys=True).encode()).hexdigest()}"
            
            # Try to get from cache
            if cache_service.use_redis and cache_service.redis_client:
                cached = cache_service.redis_client.get(cache_key)
                if cached:
                    return json.loads(cached)
            else:
                # Check memory cache
                if cache_key in _memory_cache:
                    entry = _memory_cache[cache_key]
                    if datetime.now() < entry["expires_at"]:
                        return entry["data"]
                    else:
                        del _memory_cache[cache_key]
            
            # Cache miss, execute function
            result = func(*args, **kwargs)
            
            # Store in cache
            cache_ttl = ttl or cache_service.default_ttl
            if cache_service.use_redis and cache_service.redis_client:
                cache_service.redis_client.setex(
                    cache_key,
                    cache_ttl,
                    json.dumps(result, default=str)
                )
            else:
                expires_at = datetime.now() + timedelta(seconds=cache_ttl)
                _memory_cache[cache_key] = {
                    "data": result,
                    "expires_at": expires_at,
                    "created_at": datetime.now()
                }
            
            return result
        
        return wrapper
    return decorator