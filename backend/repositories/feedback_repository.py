"""
Repository for ConversationFeedback model.
Handles all database operations for feedback.
"""
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, and_

from .base_repository import BaseRepository
from config.models import ConversationFeedback

logger = None  # Will be initialized in __init__


class FeedbackRepository(BaseRepository[ConversationFeedback]):
    """Repository for ConversationFeedback operations"""
    
    def __init__(self, session: Session):
        super().__init__(session, ConversationFeedback)
        global logger
        import logging
        logger = logging.getLogger(__name__)
    
    def get_by_conversation_id(self, conversation_id: int) -> Optional[ConversationFeedback]:
        """Get feedback by conversation ID"""
        return (
            self.session.query(self.model)
            .filter(self.model.conversation_id == conversation_id)
            .first()
        )
    
    def get_by_rating(self, rating: int, skip: int = 0, limit: int = 100) -> List[ConversationFeedback]:
        """Get feedback by rating"""
        return (
            self.session.query(self.model)
            .filter(self.model.rating == rating)
            .order_by(desc(self.model.created_at))
            .offset(skip)
            .limit(limit)
            .all()
        )
    
    def get_feedback_stats(self) -> Dict[str, Any]:
        """Get feedback statistics"""
        stats = (
            self.session.query(
                func.avg(self.model.rating).label('avg_rating'),
                func.count(self.model.id).label('total_count'),
                func.sum(func.cast(self.model.rating >= 4, func.Integer)).label('positive_count'),
                func.sum(func.cast(self.model.rating <= 2, func.Integer)).label('negative_count')
            )
            .filter(self.model.rating.isnot(None))
            .first()
        )
        
        if stats and stats.total_count > 0:
            return {
                "average_rating": float(stats.avg_rating) if stats.avg_rating else 0.0,
                "total_count": int(stats.total_count),
                "positive_count": int(stats.positive_count) if stats.positive_count else 0,
                "negative_count": int(stats.negative_count) if stats.negative_count else 0,
            }
        else:
            return {
                "average_rating": 0.0,
                "total_count": 0,
                "positive_count": 0,
                "negative_count": 0,
            }
    
    def upsert_feedback(
        self,
        conversation_id: int,
        rating: Optional[int] = None,
        feedback_type: str = "rating",
        comment: Optional[str] = None,
        user_correction: Optional[str] = None,
        is_helpful: Optional[str] = None
    ) -> ConversationFeedback:
        """Create or update feedback for a conversation"""
        from datetime import datetime
        
        existing = self.get_by_conversation_id(conversation_id)
        
        if existing:
            # Update existing feedback
            update_data = {}
            if rating is not None:
                update_data["rating"] = rating
            if feedback_type:
                update_data["feedback_type"] = feedback_type
            if comment is not None:
                update_data["comment"] = comment
            if user_correction is not None:
                update_data["user_correction"] = user_correction
            if is_helpful is not None:
                update_data["is_helpful"] = is_helpful
            
            updated = self.update(existing.id, **update_data)
            return updated if updated else existing
        else:
            # Create new feedback
            # Handle rating from feedback_type
            if feedback_type == "thumbs_up":
                rating = 1
            elif feedback_type == "thumbs_down":
                rating = -1
            elif rating is None:
                rating = 3  # Default neutral
            
            return self.create(
                conversation_id=conversation_id,
                rating=rating,
                feedback_type=feedback_type,
                comment=comment,
                user_correction=user_correction,
                is_helpful=is_helpful
            )