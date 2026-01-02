"""
Repository for AgentTask model.
Handles all database operations for tasks.
"""
from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import desc

from .base_repository import BaseRepository
from config.models import AgentTask

logger = None  # Will be initialized in __init__


class TaskRepository(BaseRepository[AgentTask]):
    """Repository for AgentTask operations"""
    
    def __init__(self, session: Session):
        super().__init__(session, AgentTask)
        global logger
        import logging
        logger = logging.getLogger(__name__)
    
    def get_by_status(self, status: str, skip: int = 0, limit: int = 100) -> List[AgentTask]:
        """Get tasks by status"""
        return (
            self.session.query(self.model)
            .filter(self.model.status == status)
            .order_by(desc(self.model.created_at))
            .offset(skip)
            .limit(limit)
            .all()
        )
    
    def update_status(self, task_id: int, status: str, result: Optional[str] = None) -> Optional[AgentTask]:
        """Update task status and optionally result"""
        update_data = {"status": status}
        if result is not None:
            update_data["result"] = result
        return self.update(task_id, **update_data)