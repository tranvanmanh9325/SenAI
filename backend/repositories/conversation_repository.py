"""
Repository for AgentConversation model.
Handles all database operations for conversations.
"""
from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import desc

from .base_repository import BaseRepository
from config.models import AgentConversation

logger = None  # Will be initialized in __init__


class ConversationRepository(BaseRepository[AgentConversation]):
    """Repository for AgentConversation operations"""
    
    def __init__(self, session: Session):
        super().__init__(session, AgentConversation)
        global logger
        import logging
        logger = logging.getLogger(__name__)
    
    def get_by_session_id(self, session_id: str, skip: int = 0, limit: int = 100) -> List[AgentConversation]:
        """Get conversations by session ID, ordered by creation date"""
        return (
            self.session.query(self.model)
            .filter(self.model.session_id == session_id)
            .order_by(desc(self.model.created_at))
            .offset(skip)
            .limit(limit)
            .all()
        )
    
    def get_recent_conversations(self, skip: int = 0, limit: int = 100) -> List[AgentConversation]:
        """Get recent conversations ordered by creation date"""
        return (
            self.session.query(self.model)
            .order_by(desc(self.model.created_at))
            .offset(skip)
            .limit(limit)
            .all()
        )
    
    def create_conversation(
        self,
        user_message: str,
        ai_response: Optional[str] = None,
        session_id: Optional[str] = None
    ) -> AgentConversation:
        """Create a new conversation"""
        return self.create(
            user_message=user_message,
            ai_response=ai_response,
            session_id=session_id
        )
    
    def update_ai_response(self, conversation_id: int, ai_response: str) -> Optional[AgentConversation]:
        """Update AI response for a conversation"""
        return self.update(conversation_id, ai_response=ai_response)