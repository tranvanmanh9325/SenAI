"""
Advanced Multi-Level Cache Service
Hỗ trợ 3 cấp cache:
- L1: In-memory cache (fast, small, per-process)
- L2: Redis cache (medium, larger, shared across processes)
- L3: Database cache (persistent, large, survives restarts)

Tính năng:
- Adaptive TTL dựa trên access patterns
- Cache warming cho frequently accessed data
- Cache invalidation strategies
- Comprehensive cache metrics và monitoring
"""
import os
import json
import hashlib
import logging
import time
import threading
from typing import Optional, Any, Dict, List
from datetime import datetime, timedelta
from collections import defaultdict
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# Import metrics service
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
        logger.debug(f"Redis auto-configuration completed, using host: {REDIS_HOST}")
    except ImportError:
        # Redis module chưa được cài, dùng default
        REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
        logger.debug(f"Redis module not available, using default host: {REDIS_HOST}")
    except Exception as e:
        logger.warning(f"Redis auto-configuration failed: {e}, using default")
        REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
else:
    REDIS_HOST = os.getenv("REDIS_HOST", "localhost")

REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_DB = int(os.getenv("REDIS_DB", "0"))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", "").strip()
if '#' in REDIS_PASSWORD:
    REDIS_PASSWORD = REDIS_PASSWORD.split('#')[0].strip()
if not REDIS_PASSWORD:
    REDIS_PASSWORD = None

# Cache configuration
L1_CACHE_SIZE = int(os.getenv("L1_CACHE_SIZE", "1000"))  # Max entries in memory
L1_DEFAULT_TTL = int(os.getenv("L1_DEFAULT_TTL", "300"))  # 5 minutes
L2_DEFAULT_TTL = int(os.getenv("L2_DEFAULT_TTL", "3600"))  # 1 hour
L3_DEFAULT_TTL = int(os.getenv("L3_DEFAULT_TTL", "86400"))  # 24 hours
L3_ENABLED = os.getenv("L3_CACHE_ENABLED", "true").lower() == "true"

# Adaptive TTL configuration
ADAPTIVE_TTL_ENABLED = os.getenv("ADAPTIVE_TTL_ENABLED", "true").lower() == "true"
MIN_TTL = int(os.getenv("MIN_TTL", "60"))  # 1 minute minimum
MAX_TTL = int(os.getenv("MAX_TTL", "86400"))  # 24 hours maximum
TTL_MULTIPLIER = float(os.getenv("TTL_MULTIPLIER", "1.5"))  # Multiply TTL for frequently accessed items

# Cache warming configuration
CACHE_WARMING_ENABLED = os.getenv("CACHE_WARMING_ENABLED", "true").lower() == "true"
WARMING_TOP_N = int(os.getenv("WARMING_TOP_N", "100"))  # Top N items to warm

# Import cache components from separate module
from .cache_components import (
    CacheLevel,
    CacheEntry,
    CacheStats,
    LRUCache,
)

# Import cache operations
from .cache_operations import CacheOperations, CacheConvenienceMethods


class AdvancedCacheService:
    """Advanced multi-level cache service"""
    
    def __init__(self, db_session=None):
        # L1: In-memory cache
        self.l1_cache = LRUCache(max_size=L1_CACHE_SIZE)
        
        # L2: Redis cache
        self.redis_client = None
        self.l2_enabled = False
        self._init_redis()
        
        # L3: Database cache
        self.db_session = db_session
        self.l3_enabled = L3_ENABLED and db_session is not None
        
        # Statistics
        self.stats = CacheStats()
        self.stats_lock = threading.Lock()
        
        # Access pattern tracking for adaptive TTL
        self.access_patterns: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
            "access_count": 0,
            "last_accessed": None,
            "avg_ttl": L2_DEFAULT_TTL
        })
        self.patterns_lock = threading.Lock()
        
        # Cache warming
        self.warming_enabled = CACHE_WARMING_ENABLED
        self._init_cache_warming()
        
        # Convenience methods for specific cache types
        self.convenience = CacheConvenienceMethods(self)
        
        logger.info(f"Advanced Cache Service initialized - L1: enabled, L2: {self.l2_enabled}, L3: {self.l3_enabled}")
    
    def _init_redis(self):
        """Initialize Redis client"""
        if not REDIS_ENABLED:
            return
        
        try:
            import redis
            
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
            
            self.redis_client = redis.Redis(**redis_kwargs)
            
            # Test connection với retry
            try:
                self.redis_client.ping()
                self.l2_enabled = True
                logger.info(f"Redis (L2) cache connected: {REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}")
            except redis.ConnectionError as e:
                logger.warning(f"Redis ping failed: {e}. L2 cache disabled.")
                self.redis_client = None
                self.l2_enabled = False
            except redis.AuthenticationError as e:
                logger.warning(f"Redis authentication failed. Please check REDIS_PASSWORD. L2 cache disabled.")
                self.redis_client = None
                self.l2_enabled = False
        except ImportError:
            logger.warning("redis package not installed. L2 cache disabled.")
        except Exception as e:
            logger.warning(f"Redis connection failed: {e}. L2 cache disabled.")
            self.redis_client = None
            self.l2_enabled = False
    
    def _init_cache_warming(self):
        """Initialize cache warming"""
        if self.warming_enabled:
            # Start background thread for cache warming
            self.warming_thread = threading.Thread(target=self._cache_warming_worker, daemon=True)
            self.warming_thread.start()
            logger.info("Cache warming enabled")
    
    def _generate_key(self, prefix: str, *args, **kwargs) -> str:
        """Generate cache key from prefix and arguments"""
        key_parts = [prefix]
        
        for arg in args:
            if isinstance(arg, (dict, list)):
                key_parts.append(json.dumps(arg, sort_keys=True))
            else:
                key_parts.append(str(arg))
        
        if kwargs:
            sorted_kwargs = sorted(kwargs.items())
            key_parts.append(json.dumps(sorted_kwargs, sort_keys=True))
        
        key_string = ":".join(key_parts)
        if len(key_string) > 200:
            key_hash = hashlib.md5(key_string.encode()).hexdigest()
            return f"{prefix}:{key_hash}"
        
        return key_string
    
    def _calculate_adaptive_ttl(self, key: str, base_ttl: int, cache_type: str) -> int:
        """Calculate adaptive TTL based on access patterns"""
        if not ADAPTIVE_TTL_ENABLED:
            return base_ttl
        
        with self.patterns_lock:
            pattern = self.access_patterns[key]
            access_count = pattern["access_count"]
            
            # Increase TTL for frequently accessed items
            if access_count > 10:
                # Very frequently accessed: increase TTL significantly
                adaptive_ttl = int(base_ttl * TTL_MULTIPLIER * 2)
            elif access_count > 5:
                # Frequently accessed: increase TTL moderately
                adaptive_ttl = int(base_ttl * TTL_MULTIPLIER)
            else:
                # Normal access: use base TTL
                adaptive_ttl = base_ttl
            
            # Clamp to min/max
            adaptive_ttl = max(MIN_TTL, min(MAX_TTL, adaptive_ttl))
            
            return adaptive_ttl
    
    def _update_access_pattern(self, key: str, cache_type: str):
        """Update access pattern for adaptive TTL"""
        with self.patterns_lock:
            pattern = self.access_patterns[key]
            pattern["access_count"] += 1
            pattern["last_accessed"] = datetime.now()
            pattern["cache_type"] = cache_type
    
    def get(self, key: str, cache_type: str = "generic") -> Optional[Any]:
        """Get value from cache (tries L1 -> L2 -> L3)"""
        # Try L1 first
        value = self.l1_cache.get(key)
        if value is not None:
            with self.stats_lock:
                self.stats.hits += 1
                self.stats.l1_hits += 1
            self._update_access_pattern(key, cache_type)
            self._record_cache_hit("l1", cache_type)
            return value
        
        with self.stats_lock:
            self.stats.l1_misses += 1
        
        # Try L2 (Redis)
        if self.l2_enabled:
            value = CacheOperations.get_from_l2(self.redis_client, key)
            if value is not None:
                # Promote to L1
                ttl = self._calculate_adaptive_ttl(key, L1_DEFAULT_TTL, cache_type)
                self.l1_cache.set(key, value, ttl, cache_type)
                
                with self.stats_lock:
                    self.stats.hits += 1
                    self.stats.l2_hits += 1
                self._update_access_pattern(key, cache_type)
                self._record_cache_hit("l2", cache_type)
                return value
        
        with self.stats_lock:
            self.stats.l2_misses += 1
        
        # Try L3 (Database)
        if self.l3_enabled:
            value = CacheOperations.get_from_l3(self.db_session, key)
            if value is not None:
                # Promote to L1 and L2
                ttl_l1 = self._calculate_adaptive_ttl(key, L1_DEFAULT_TTL, cache_type)
                ttl_l2 = self._calculate_adaptive_ttl(key, L2_DEFAULT_TTL, cache_type)
                self.l1_cache.set(key, value, ttl_l1, cache_type)
                if self.l2_enabled:
                    CacheOperations.set_to_l2(self.redis_client, key, value, ttl_l2)
                
                with self.stats_lock:
                    self.stats.hits += 1
                    self.stats.l3_hits += 1
                self._update_access_pattern(key, cache_type)
                self._record_cache_hit("l3", cache_type)
                return value
        
        with self.stats_lock:
            self.stats.misses += 1
            self.stats.l3_misses += 1
        
        self._record_cache_miss(cache_type)
        return None
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None, 
            cache_type: str = "generic", levels: List[CacheLevel] = None) -> bool:
        """Set value in cache at specified levels"""
        if levels is None:
            # Default: set in all available levels
            levels = [CacheLevel.L1]
            if self.l2_enabled:
                levels.append(CacheLevel.L2)
            if self.l3_enabled:
                levels.append(CacheLevel.L3)
        
        # Calculate adaptive TTL
        base_ttl = ttl or L2_DEFAULT_TTL
        adaptive_ttl = self._calculate_adaptive_ttl(key, base_ttl, cache_type)
        
        success = True
        
        # Set in L1
        if CacheLevel.L1 in levels:
            l1_ttl = adaptive_ttl if adaptive_ttl < L1_DEFAULT_TTL * 2 else L1_DEFAULT_TTL
            success = self.l1_cache.set(key, value, l1_ttl, cache_type) and success
        
        # Set in L2
        if CacheLevel.L2 in levels and self.l2_enabled:
            l2_ttl = adaptive_ttl
            success = CacheOperations.set_to_l2(self.redis_client, key, value, l2_ttl) and success
        
        # Set in L3
        if CacheLevel.L3 in levels and self.l3_enabled:
            l3_ttl = adaptive_ttl if adaptive_ttl > L2_DEFAULT_TTL else L3_DEFAULT_TTL
            success = CacheOperations.set_to_l3(self.db_session, key, value, l3_ttl, cache_type) and success
        
        if success:
            with self.stats_lock:
                self.stats.sets += 1
        
        return success
    
    
    def delete(self, key: str, levels: List[CacheLevel] = None) -> bool:
        """Delete key from cache at specified levels"""
        if levels is None:
            levels = [CacheLevel.L1, CacheLevel.L2, CacheLevel.L3]
        
        success = True
        
        if CacheLevel.L1 in levels:
            success = self.l1_cache.delete(key) and success
        
        if CacheLevel.L2 in levels and self.l2_enabled:
            if not CacheOperations.delete_from_l2(self.redis_client, key):
                success = False
        
        if CacheLevel.L3 in levels and self.l3_enabled:
            if not CacheOperations.delete_from_l3(self.db_session, key):
                success = False
                self.l3_enabled = False
        
        return success
    
    def invalidate_pattern(self, pattern: str, levels: List[CacheLevel] = None) -> int:
        """Invalidate cache entries matching pattern"""
        if levels is None:
            levels = [CacheLevel.L1, CacheLevel.L2, CacheLevel.L3]
        
        count = 0
        
        # L1: iterate through all keys
        if CacheLevel.L1 in levels:
            keys_to_delete = [k for k in self.l1_cache.cache.keys() if pattern in k]
            for key in keys_to_delete:
                if self.l1_cache.delete(key):
                    count += 1
        
        # L2: use Redis pattern matching
        if CacheLevel.L2 in levels and self.l2_enabled:
            count += CacheOperations.invalidate_pattern_l2(self.redis_client, pattern)
        
        # L3: database query
        if CacheLevel.L3 in levels and self.l3_enabled:
            deleted = CacheOperations.invalidate_pattern_l3(self.db_session, pattern)
            if deleted == 0:
                self.l3_enabled = False
            count += deleted
        
        return count
    
    def _record_cache_hit(self, level: str, cache_type: str):
        """Record cache hit metric"""
        if METRICS_AVAILABLE and metrics_service:
            metrics_service.record_cache_hit(f"{level}:{cache_type}")
    
    def _record_cache_miss(self, cache_type: str):
        """Record cache miss metric"""
        if METRICS_AVAILABLE and metrics_service:
            metrics_service.record_cache_miss(cache_type)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        with self.stats_lock:
            stats_dict = {
                "hits": self.stats.hits,
                "misses": self.stats.misses,
                "sets": self.stats.sets,
                "evictions": self.stats.evictions,
                "hit_rate": self.stats.get_hit_rate(),
                "l1": {
                    "hits": self.stats.l1_hits,
                    "misses": self.stats.l1_misses,
                    "size": self.l1_cache.size(),
                    "max_size": self.l1_cache.max_size
                },
                "l2": {
                    "enabled": self.l2_enabled,
                    "hits": self.stats.l2_hits,
                    "misses": self.stats.l2_misses
                },
                "l3": {
                    "enabled": self.l3_enabled,
                    "hits": self.stats.l3_hits,
                    "misses": self.stats.l3_misses
                }
            }
            
            if self.l2_enabled:
                try:
                    info = self.redis_client.info("memory")
                    stats_dict["l2"]["memory_used"] = info.get("used_memory_human", "N/A")
                except:
                    pass
            
            return stats_dict
    
    def _cache_warming_worker(self):
        """Background worker for cache warming"""
        import time
        
        while True:
            try:
                time.sleep(300)  # Run every 5 minutes
                if self.warming_enabled:
                    self._warm_cache()
            except Exception as e:
                logger.error(f"Cache warming worker error: {e}")
    
    def _warm_cache(self):
        """Warm cache with frequently accessed items"""
        CacheOperations.warm_cache(
            self.l1_cache,
            self.l2_enabled,
            self.redis_client,
            self.db_session,
            self.l3_enabled,
            L1_DEFAULT_TTL,
            L2_DEFAULT_TTL,
            WARMING_TOP_N
        )
    
    def warm_cache_now(self) -> Dict[str, Any]:
        """Manually trigger cache warming"""
        start_time = time.time()
        self._warm_cache()
        duration = time.time() - start_time
        
        return {
            "status": "completed",
            "duration_seconds": duration,
            "timestamp": datetime.now().isoformat()
        }
    
    # Convenience methods for backward compatibility
    def get_embedding_key(self, text: str) -> str:
        """Generate cache key for embedding"""
        return self.convenience.get_embedding_key(text)
    
    def get_llm_response_key(self, user_message: str, conversation_history: Optional[list] = None,
                             system_prompt: Optional[str] = None, temperature: float = 0.7) -> str:
        """Generate cache key for LLM response"""
        return self.convenience.get_llm_response_key(user_message, conversation_history, system_prompt, temperature)
    
    def get_pattern_analysis_key(self, session_id: str, limit: int = 10) -> str:
        """Generate cache key for pattern analysis"""
        return self.convenience.get_pattern_analysis_key(session_id, limit)
    
    def cache_embedding(self, text: str, embedding: list, ttl: Optional[int] = None) -> bool:
        """Cache embedding result"""
        return self.convenience.cache_embedding(text, embedding, ttl)
    
    def get_cached_embedding(self, text: str) -> Optional[list]:
        """Get cached embedding"""
        return self.convenience.get_cached_embedding(text)
    
    def cache_llm_response(self, user_message: str, response: str,
                          conversation_history: Optional[list] = None,
                          system_prompt: Optional[str] = None,
                          temperature: float = 0.7,
                          ttl: Optional[int] = None) -> bool:
        """Cache LLM response"""
        return self.convenience.cache_llm_response(user_message, response, conversation_history,
                                                   system_prompt, temperature, ttl)
    
    def get_cached_llm_response(self, user_message: str,
                               conversation_history: Optional[list] = None,
                               system_prompt: Optional[str] = None,
                               temperature: float = 0.7) -> Optional[str]:
        """Get cached LLM response"""
        return self.convenience.get_cached_llm_response(user_message, conversation_history,
                                                        system_prompt, temperature)
    
    def cache_pattern_analysis(self, session_id: str, analysis: Dict[str, Any],
                              limit: int = 10, ttl: Optional[int] = None) -> bool:
        """Cache pattern analysis result"""
        return self.convenience.cache_pattern_analysis(session_id, analysis, limit, ttl)
    
    def get_cached_pattern_analysis(self, session_id: str, limit: int = 10) -> Optional[Dict[str, Any]]:
        """Get cached pattern analysis"""
        return self.convenience.get_cached_pattern_analysis(session_id, limit)
    
    def invalidate_llm_cache_by_pattern(self, pattern: str) -> int:
        """Smart invalidation: Invalidate LLM cache entries matching pattern"""
        return self.convenience.invalidate_llm_cache_by_pattern(pattern)
    
    def invalidate_llm_cache_for_user_message(self, user_message: str) -> int:
        """Invalidate all LLM cache entries for a specific user message"""
        return self.convenience.invalidate_llm_cache_for_user_message(user_message)
    
    def invalidate_stale_llm_cache(self, max_age_hours: int = 168) -> int:
        """Invalidate stale LLM cache entries older than specified age"""
        return self.convenience.invalidate_stale_llm_cache(max_age_hours)


# Global instance (will be initialized with db_session when needed)
_advanced_cache_service = None


def get_advanced_cache_service(db_session=None) -> AdvancedCacheService:
    """Get or create advanced cache service instance"""
    global _advanced_cache_service
    
    if _advanced_cache_service is None:
        _advanced_cache_service = AdvancedCacheService(db_session=db_session)
    elif db_session is not None and _advanced_cache_service.db_session is None:
        # Update db_session if provided
        _advanced_cache_service.db_session = db_session
        _advanced_cache_service.l3_enabled = L3_ENABLED
    
    return _advanced_cache_service