"""
Feedback Service để học từ đánh giá của user
Phân tích feedback và cải thiện responses
"""
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import func, text
from sqlalchemy import and_

logger = logging.getLogger(__name__)

class FeedbackService:
    """Service để quản lý và phân tích feedback"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def submit_feedback(
        self,
        conversation_id: int,
        rating: Optional[int] = None,
        feedback_type: str = "rating",
        comment: Optional[str] = None,
        user_correction: Optional[str] = None,
        is_helpful: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Submit feedback cho một conversation
        
        Args:
            conversation_id: ID của conversation
            rating: Điểm đánh giá (1-5) hoặc -1 (thumbs down), 1 (thumbs up)
            feedback_type: Loại feedback (rating, thumbs_up, thumbs_down, detailed)
            comment: Comment chi tiết
            user_correction: Câu trả lời đúng nếu user muốn sửa
            is_helpful: Có hữu ích không (yes, no, partially)
            
        Returns:
            Dict với thông tin feedback đã tạo
        """
        try:
            # Kiểm tra conversation có tồn tại không
            from app import AgentConversation
            conversation = self.db.query(AgentConversation).filter(
                AgentConversation.id == conversation_id
            ).first()
            
            if not conversation:
                return {
                    "success": False,
                    "error": f"Conversation {conversation_id} not found"
                }
            
            # Kiểm tra đã có feedback chưa (có thể update)
            from app import ConversationFeedback
            existing_feedback = self.db.query(ConversationFeedback).filter(
                ConversationFeedback.conversation_id == conversation_id
            ).first()
            
            if existing_feedback:
                # Update existing feedback
                if rating is not None:
                    existing_feedback.rating = rating
                if feedback_type:
                    existing_feedback.feedback_type = feedback_type
                if comment is not None:
                    existing_feedback.comment = comment
                if user_correction is not None:
                    existing_feedback.user_correction = user_correction
                if is_helpful is not None:
                    existing_feedback.is_helpful = is_helpful
                existing_feedback.updated_at = datetime.utcnow()
                
                self.db.commit()
                self.db.refresh(existing_feedback)
                
                return {
                    "success": True,
                    "message": "Feedback updated",
                    "feedback_id": existing_feedback.id
                }
            else:
                # Tạo feedback mới
                # Xử lý rating từ feedback_type
                if feedback_type == "thumbs_up":
                    rating = 1
                elif feedback_type == "thumbs_down":
                    rating = -1
                elif rating is None:
                    rating = 3  # Default neutral
                
                feedback = ConversationFeedback(
                    conversation_id=conversation_id,
                    rating=rating,
                    feedback_type=feedback_type,
                    comment=comment,
                    user_correction=user_correction,
                    is_helpful=is_helpful
                )
                
                self.db.add(feedback)
                self.db.commit()
                self.db.refresh(feedback)
                
                return {
                    "success": True,
                    "message": "Feedback submitted",
                    "feedback_id": feedback.id
                }
        except Exception as e:
            logger.error(f"Error submitting feedback: {e}")
            self.db.rollback()
            return {
                "success": False,
                "error": str(e)
            }
    
    def get_feedback_stats(self, conversation_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Lấy thống kê feedback
        
        Args:
            conversation_id: Filter theo conversation (None = tất cả)
            
        Returns:
            Dict với thống kê
        """
        try:
            from app import ConversationFeedback
            
            query = self.db.query(ConversationFeedback)
            
            if conversation_id:
                query = query.filter(ConversationFeedback.conversation_id == conversation_id)
            
            # Total feedback
            total = query.count()
            
            if total == 0:
                return {
                    "total_feedback": 0,
                    "average_rating": None,
                    "positive_count": 0,
                    "negative_count": 0,
                    "neutral_count": 0,
                    "helpful_count": 0,
                    "not_helpful_count": 0,
                    "feedback_by_type": {}
                }
            
            # Average rating (chỉ tính rating > 0)
            avg_rating = self.db.query(func.avg(ConversationFeedback.rating)).filter(
                ConversationFeedback.rating > 0
            ).scalar()
            
            # Count by sentiment
            positive = query.filter(
                ConversationFeedback.rating >= 4
            ).count()
            
            negative = query.filter(
                ConversationFeedback.rating <= 2
            ).count()
            
            neutral = query.filter(
                and_(ConversationFeedback.rating > 2, ConversationFeedback.rating < 4)
            ).count()
            
            # Count by helpfulness
            helpful = query.filter(
                ConversationFeedback.is_helpful == "yes"
            ).count()
            
            not_helpful = query.filter(
                ConversationFeedback.is_helpful == "no"
            ).count()
            
            # Count by type
            feedback_by_type = {}
            types = self.db.query(
                ConversationFeedback.feedback_type,
                func.count(ConversationFeedback.id)
            ).group_by(ConversationFeedback.feedback_type).all()
            
            for fb_type, count in types:
                feedback_by_type[fb_type] = count
            
            return {
                "total_feedback": total,
                "average_rating": float(avg_rating) if avg_rating else None,
                "positive_count": positive,
                "negative_count": negative,
                "neutral_count": neutral,
                "helpful_count": helpful,
                "not_helpful_count": not_helpful,
                "feedback_by_type": feedback_by_type
            }
        except Exception as e:
            logger.error(f"Error getting feedback stats: {e}")
            return {
                "error": str(e)
            }
    
    def get_feedback_for_training(
        self,
        min_rating: int = 3,
        include_corrections: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Lấy feedback để sử dụng trong training/fine-tuning
        
        Args:
            min_rating: Rating tối thiểu để include (default 3)
            include_corrections: Có include user corrections không
            
        Returns:
            List các feedback phù hợp cho training
        """
        try:
            from app import ConversationFeedback, AgentConversation
            
            # Lấy feedback có rating tốt hoặc có correction
            query = self.db.query(ConversationFeedback).join(
                AgentConversation,
                ConversationFeedback.conversation_id == AgentConversation.id
            )
            
            conditions = []
            if min_rating:
                conditions.append(ConversationFeedback.rating >= min_rating)
            if include_corrections:
                conditions.append(ConversationFeedback.user_correction.isnot(None))
            
            if conditions:
                from sqlalchemy import or_
                query = query.filter(or_(*conditions))
            
            feedbacks = query.all()
            
            training_data = []
            for fb in feedbacks:
                # Lấy conversation
                conv = self.db.query(AgentConversation).filter(
                    AgentConversation.id == fb.conversation_id
                ).first()
                
                if conv:
                    item = {
                        "conversation_id": fb.conversation_id,
                        "user_message": conv.user_message,
                        "original_response": conv.ai_response,
                        "rating": fb.rating,
                        "feedback_type": fb.feedback_type,
                        "comment": fb.comment,
                        "is_helpful": fb.is_helpful
                    }
                    
                    # Nếu có user correction, dùng nó làm output đúng
                    if fb.user_correction:
                        item["corrected_response"] = fb.user_correction
                        item["should_use_correction"] = True
                    else:
                        item["should_use_correction"] = False
                    
                    training_data.append(item)
            
            return training_data
        except Exception as e:
            logger.error(f"Error getting feedback for training: {e}")
            return []
    
    def get_conversations_with_feedback(
        self,
        rating_threshold: Optional[int] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Lấy conversations kèm feedback để review
        
        Args:
            rating_threshold: Filter theo rating (None = tất cả)
            limit: Số lượng tối đa
            
        Returns:
            List conversations với feedback
        """
        try:
            from app import ConversationFeedback, AgentConversation
            
            query = self.db.query(
                AgentConversation,
                ConversationFeedback
            ).join(
                ConversationFeedback,
                AgentConversation.id == ConversationFeedback.conversation_id
            )
            
            if rating_threshold is not None:
                query = query.filter(ConversationFeedback.rating >= rating_threshold)
            
            results = query.order_by(
                ConversationFeedback.created_at.desc()
            ).limit(limit).all()
            
            conversations = []
            for conv, fb in results:
                conversations.append({
                    "conversation_id": conv.id,
                    "user_message": conv.user_message,
                    "ai_response": conv.ai_response,
                    "session_id": conv.session_id,
                    "created_at": conv.created_at.isoformat(),
                    "feedback": {
                        "id": fb.id,
                        "rating": fb.rating,
                        "feedback_type": fb.feedback_type,
                        "comment": fb.comment,
                        "user_correction": fb.user_correction,
                        "is_helpful": fb.is_helpful,
                        "created_at": fb.created_at.isoformat()
                    }
                })
            
            return conversations
        except Exception as e:
            logger.error(f"Error getting conversations with feedback: {e}")
            return []