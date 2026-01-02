"""
Repository for APIKey and APIKeyAuditLog models.
Handles all database operations for API keys.
"""
from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import desc
from datetime import datetime

from .base_repository import BaseRepository
from config.models import APIKey, APIKeyAuditLog

logger = None  # Will be initialized in __init__


class APIKeyRepository(BaseRepository[APIKey]):
    """Repository for APIKey operations"""
    
    def __init__(self, session: Session):
        super().__init__(session, APIKey)
        global logger
        import logging
        logger = logging.getLogger(__name__)
    
    def get_by_key_hash(self, key_hash: str) -> Optional[APIKey]:
        """Get API key by key hash"""
        return (
            self.session.query(self.model)
            .filter(self.model.key_hash == key_hash)
            .filter(self.model.is_active == True)  # Only active keys
            .first()
        )
    
    def get_active_keys(self, skip: int = 0, limit: int = 100) -> List[APIKey]:
        """Get all active API keys"""
        return (
            self.session.query(self.model)
            .filter(self.model.is_active == True)
            .order_by(desc(self.model.created_at))
            .offset(skip)
            .limit(limit)
            .all()
        )
    
    def deactivate_key(self, key_id: int) -> Optional[APIKey]:
        """Deactivate an API key"""
        return self.update(key_id, is_active=False)
    
    def update_last_used(self, key_id: int) -> Optional[APIKey]:
        """Update last used timestamp"""
        return self.update(key_id, last_used_at=datetime.utcnow())


class APIKeyAuditLogRepository(BaseRepository[APIKeyAuditLog]):
    """Repository for APIKeyAuditLog operations"""
    
    def __init__(self, session: Session):
        super().__init__(session, APIKeyAuditLog)
        global logger
        import logging
        logger = logging.getLogger(__name__)
    
    def create_audit_log(
        self,
        api_key_id: int,
        endpoint: str,
        method: str,
        status_code: int,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        response_time_ms: Optional[int] = None
    ) -> APIKeyAuditLog:
        """Create a new audit log entry"""
        return self.create(
            api_key_id=api_key_id,
            endpoint=endpoint,
            method=method,
            status_code=status_code,
            ip_address=ip_address,
            user_agent=user_agent,
            response_time_ms=response_time_ms
        )
    
    def get_by_api_key_id(self, api_key_id: int, skip: int = 0, limit: int = 100) -> List[APIKeyAuditLog]:
        """Get audit logs by API key ID"""
        return (
            self.session.query(self.model)
            .filter(self.model.api_key_id == api_key_id)
            .order_by(desc(self.model.created_at))
            .offset(skip)
            .limit(limit)
            .all()
        )