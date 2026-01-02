"""
Repository for CacheEntry model.
Handles all database operations for cache entries (L3 cache).
"""
from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import and_
from datetime import datetime

from .base_repository import BaseRepository
from config.models import CacheEntry

logger = None  # Will be initialized in __init__


class CacheRepository(BaseRepository[CacheEntry]):
    """Repository for CacheEntry operations"""
    
    def __init__(self, session: Session):
        super().__init__(session, CacheEntry)
        global logger
        import logging
        logger = logging.getLogger(__name__)
    
    def get_by_key(self, cache_key: str) -> Optional[CacheEntry]:
        """Get cache entry by key"""
        entry = (
            self.session.query(self.model)
            .filter(self.model.cache_key == cache_key)
            .first()
        )
        
        # Check if expired
        if entry and entry.expires_at < datetime.utcnow():
            # Delete expired entry
            try:
                self.session.delete(entry)
                self.session.commit()
                return None
            except Exception as e:
                self.session.rollback()
                logger.error(f"Error deleting expired cache entry: {e}")
                return None
        
        return entry
    
    def get_by_type(self, cache_type: str, skip: int = 0, limit: int = 100) -> List[CacheEntry]:
        """Get cache entries by type"""
        return (
            self.session.query(self.model)
            .filter(self.model.cache_type == cache_type)
            .filter(self.model.expires_at > datetime.utcnow())  # Only non-expired
            .offset(skip)
            .limit(limit)
            .all()
        )
    
    def upsert_cache_entry(
        self,
        cache_key: str,
        cache_value: str,
        cache_type: str,
        expires_at: datetime
    ) -> CacheEntry:
        """Create or update cache entry"""
        existing = self.get_by_key(cache_key)
        
        if existing:
            # Update existing entry
            return self.update(
                existing.id,
                cache_value=cache_value,
                cache_type=cache_type,
                expires_at=expires_at,
                access_count=existing.access_count + 1,
                last_accessed=datetime.utcnow()
            )
        else:
            # Create new entry
            return self.create(
                cache_key=cache_key,
                cache_value=cache_value,
                cache_type=cache_type,
                expires_at=expires_at,
                access_count=1,
                last_accessed=datetime.utcnow()
            )
    
    def increment_access_count(self, cache_key: str) -> Optional[CacheEntry]:
        """Increment access count for a cache entry"""
        entry = self.get_by_key(cache_key)
        if entry:
            return self.update(
                entry.id,
                access_count=entry.access_count + 1,
                last_accessed=datetime.utcnow()
            )
        return None
    
    def delete_expired(self) -> int:
        """Delete expired cache entries and return count"""
        try:
            deleted_count = (
                self.session.query(self.model)
                .filter(self.model.expires_at < datetime.utcnow())
                .delete()
            )
            self.session.commit()
            return deleted_count
        except Exception as e:
            self.session.rollback()
            logger.error(f"Error deleting expired cache entries: {e}")
            return 0