"""
Cache components and utilities.
This module contains cache data structures, enums, and the LRU cache implementation
used by the advanced cache service.
"""
import threading
from typing import Optional, Any, List, Tuple
from datetime import datetime, timedelta
from collections import OrderedDict
from dataclasses import dataclass
from enum import Enum


class CacheLevel(Enum):
    """Cache level enumeration"""
    L1 = "l1"  # In-memory
    L2 = "l2"  # Redis
    L3 = "l3"  # Database


@dataclass
class CacheEntry:
    """Cache entry metadata"""
    key: str
    value: Any
    created_at: datetime
    expires_at: datetime
    access_count: int = 0
    last_accessed: datetime = None
    cache_type: str = "generic"
    ttl: int = None
    
    def __post_init__(self):
        if self.last_accessed is None:
            self.last_accessed = self.created_at


@dataclass
class CacheStats:
    """Cache statistics"""
    hits: int = 0
    misses: int = 0
    sets: int = 0
    evictions: int = 0
    l1_hits: int = 0
    l2_hits: int = 0
    l3_hits: int = 0
    l1_misses: int = 0
    l2_misses: int = 0
    l3_misses: int = 0
    
    def get_hit_rate(self) -> float:
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0


class LRUCache:
    """LRU Cache implementation for L1"""
    
    def __init__(self, max_size: int = 1000):
        self.max_size = max_size
        self.cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self.lock = threading.RLock()
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        with self.lock:
            if key not in self.cache:
                return None
            
            entry = self.cache[key]
            
            # Check expiration
            if datetime.now() > entry.expires_at:
                del self.cache[key]
                return None
            
            # Move to end (most recently used)
            self.cache.move_to_end(key)
            
            # Update access stats
            entry.access_count += 1
            entry.last_accessed = datetime.now()
            
            return entry.value
    
    def set(self, key: str, value: Any, ttl: int, cache_type: str = "generic") -> bool:
        """Set value in cache"""
        with self.lock:
            # Remove if exists
            if key in self.cache:
                del self.cache[key]
            
            # Evict if at capacity
            while len(self.cache) >= self.max_size:
                # Remove oldest (first item)
                oldest_key = next(iter(self.cache))
                del self.cache[oldest_key]
            
            # Add new entry
            expires_at = datetime.now() + timedelta(seconds=ttl)
            entry = CacheEntry(
                key=key,
                value=value,
                created_at=datetime.now(),
                expires_at=expires_at,
                cache_type=cache_type,
                ttl=ttl
            )
            self.cache[key] = entry
            
            return True
    
    def delete(self, key: str) -> bool:
        """Delete key from cache"""
        with self.lock:
            if key in self.cache:
                del self.cache[key]
                return True
            return False
    
    def clear(self) -> int:
        """Clear all entries"""
        with self.lock:
            count = len(self.cache)
            self.cache.clear()
            return count
    
    def size(self) -> int:
        """Get current cache size"""
        return len(self.cache)
    
    def get_access_stats(self) -> List[Tuple[str, int]]:
        """Get access statistics sorted by access count"""
        with self.lock:
            stats = [(key, entry.access_count) for key, entry in self.cache.items()]
            return sorted(stats, key=lambda x: x[1], reverse=True)