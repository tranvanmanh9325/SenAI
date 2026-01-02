"""
Feedback Service để học từ đánh giá của user
Phân tích feedback và cải thiện responses
"""
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

from repositories import FeedbackRepository, ConversationRepository
from services.encryption_service import encryption_service

logger = logging.getLogger(__name__)

class FeedbackService:
    """Service để quản lý và phân tích feedback"""
    
    def __init__(
        self,
        feedback_repository: Optional[FeedbackRepository] = None,
        conversation_repository: Optional[ConversationRepository] = None,
        db: Optional[Any] = None
    ):
        """
        Initialize FeedbackService with repositories or database session (for backward compatibility)
        
        Args:
            feedback_repository: Repository for feedback operations (preferred)
            conversation_repository: Repository for conversation operations (preferred)
            db: Database session (for backward compatibility, will create repos if not provided)
        """
        from sqlalchemy.orm import Session
        
        if feedback_repository is not None and conversation_repository is not None:
            # New pattern: use repositories
            self.feedback_repo = feedback_repository
            self.conversation_repo = conversation_repository
            self.db = feedback_repository.session
        elif db is not None:
            # Backward compatibility: create repositories from session
            from repositories import FeedbackRepository, ConversationRepository
            self.db = db
            self.feedback_repo = FeedbackRepository(db)
            self.conversation_repo = ConversationRepository(db)
        else:
            raise ValueError("Either provide repositories or a database session")
    
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
            conversation = self.conversation_repo.get_by_id(conversation_id)
            
            if not conversation:
                return {
                    "success": False,
                    "error": f"Conversation {conversation_id} not found"
                }
            
            # Encrypt sensitive fields before saving
            encrypted_comment = encryption_service.encrypt(comment) if comment else None
            encrypted_user_correction = encryption_service.encrypt(user_correction) if user_correction else None
            
            # Use repository to upsert feedback
            feedback = self.feedback_repo.upsert_feedback(
                conversation_id=conversation_id,
                rating=rating,
                feedback_type=feedback_type,
                comment=encrypted_comment,
                user_correction=encrypted_user_correction,
                is_helpful=is_helpful
            )
            
            return {
                "success": True,
                "message": "Feedback submitted",
                "feedback_id": feedback.id
            }
        except Exception as e:
            logger.error(f"Error submitting feedback: {e}")
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
            from sqlalchemy import func, and_
            from models import ConversationFeedback
            
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
            
            # Use repository method for general stats, then filter if needed
            stats = self.feedback_repo.get_feedback_stats()
            
            # If filtering by conversation_id, we need custom query
            if conversation_id:
                filtered_query = self.db.query(ConversationFeedback).filter(
                    ConversationFeedback.conversation_id == conversation_id
                )
                total = filtered_query.count()
                avg_rating = filtered_query.filter(
                    ConversationFeedback.rating > 0
                ).with_entities(func.avg(ConversationFeedback.rating)).scalar()
                positive = filtered_query.filter(ConversationFeedback.rating >= 4).count()
                negative = filtered_query.filter(ConversationFeedback.rating <= 2).count()
                neutral = filtered_query.filter(
                    and_(ConversationFeedback.rating > 2, ConversationFeedback.rating < 4)
                ).count()
                helpful = filtered_query.filter(ConversationFeedback.is_helpful == "yes").count()
                not_helpful = filtered_query.filter(ConversationFeedback.is_helpful == "no").count()
                
                # Count by type
                feedback_by_type = {}
                types = filtered_query.with_entities(
                    ConversationFeedback.feedback_type,
                    func.count(ConversationFeedback.id)
                ).group_by(ConversationFeedback.feedback_type).all()
                
                for fb_type, count in types:
                    feedback_by_type[fb_type] = count
            else:
                # Use repository stats
                avg_rating = stats.get("average_rating")
                total = stats.get("total_count", 0)
                positive = stats.get("positive_count", 0)
                negative = stats.get("negative_count", 0)
                neutral = total - positive - negative
                helpful = self.db.query(ConversationFeedback).filter(
                    ConversationFeedback.is_helpful == "yes"
                ).count()
                not_helpful = self.db.query(ConversationFeedback).filter(
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
            from models import ConversationFeedback, AgentConversation
            
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
                    # Decrypt sensitive fields
                    decrypted_comment = None
                    decrypted_user_correction = None
                    
                    try:
                        if fb.comment:
                            decrypted_comment = encryption_service.decrypt(fb.comment)
                        if fb.user_correction:
                            decrypted_user_correction = encryption_service.decrypt(fb.user_correction)
                    except Exception as e:
                        logger.warning(f"Error decrypting feedback {fb.id} for training: {e}")
                        # Fallback to original (may be unencrypted old data)
                        decrypted_comment = fb.comment
                        decrypted_user_correction = fb.user_correction
                    
                    item = {
                        "conversation_id": fb.conversation_id,
                        "user_message": conv.user_message,
                        "original_response": conv.ai_response,
                        "rating": fb.rating,
                        "feedback_type": fb.feedback_type,
                        "comment": decrypted_comment,
                        "is_helpful": fb.is_helpful
                    }
                    
                    # Nếu có user correction, dùng nó làm output đúng
                    if decrypted_user_correction:
                        item["corrected_response"] = decrypted_user_correction
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
            from models import ConversationFeedback, AgentConversation
            
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
                # Decrypt sensitive fields when reading
                decrypted_comment = None
                decrypted_user_correction = None
                
                try:
                    if fb.comment:
                        decrypted_comment = encryption_service.decrypt(fb.comment)
                    if fb.user_correction:
                        decrypted_user_correction = encryption_service.decrypt(fb.user_correction)
                except Exception as e:
                    logger.warning(f"Error decrypting feedback {fb.id}: {e}")
                    # Fallback to original (may be unencrypted old data)
                    decrypted_comment = fb.comment
                    decrypted_user_correction = fb.user_correction
                
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
                        "comment": decrypted_comment,
                        "user_correction": decrypted_user_correction,
                        "is_helpful": fb.is_helpful,
                        "created_at": fb.created_at.isoformat()
                    }
                })
            
            return conversations
        except Exception as e:
            logger.error(f"Error getting conversations with feedback: {e}")
            return []