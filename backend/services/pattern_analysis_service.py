"""
Pattern Analysis Service để phân tích patterns từ conversations
Phát hiện common questions, topics, intent và cải thiện responses
Có tích hợp Redis caching để tăng hiệu năng
"""
import logging
import re
from typing import List, Dict, Any, Optional, Tuple
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import text, func, and_

logger = logging.getLogger(__name__)

# Import cache service nếu có
try:
    from .cache_service import cache_service
    CACHE_AVAILABLE = True
except ImportError:
    CACHE_AVAILABLE = False
    cache_service = None
    logger.warning("Cache service not available. Install redis package for caching support.")

class PatternAnalysisService:
    """Service để phân tích patterns từ conversations"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def analyze_common_questions(
        self,
        min_frequency: int = 2,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Phân tích các câu hỏi thường gặp
        
        Args:
            min_frequency: Tần suất tối thiểu
            limit: Số lượng kết quả tối đa
            
        Returns:
            List các câu hỏi thường gặp với frequency
        """
        try:
            # Lấy tất cả user messages
            conversations = self.db.execute(
                text("""
                    SELECT user_message, COUNT(*) as frequency
                    FROM agent_conversations
                    WHERE user_message IS NOT NULL AND user_message != ''
                    GROUP BY LOWER(TRIM(user_message))
                    HAVING COUNT(*) >= :min_freq
                    ORDER BY frequency DESC
                    LIMIT :limit
                """),
                {"min_freq": min_frequency, "limit": limit}
            ).fetchall()
            
            common_questions = []
            for msg, freq in conversations:
                # Phát hiện câu hỏi (có dấu hỏi hoặc từ khóa hỏi)
                if self._is_question(msg):
                    common_questions.append({
                        "question": msg,
                        "frequency": freq,
                        "type": "question"
                    })
            
            return sorted(common_questions, key=lambda x: x["frequency"], reverse=True)
        except Exception as e:
            logger.error(f"Error analyzing common questions: {e}")
            return []
    
    def analyze_topics(
        self,
        min_occurrences: int = 3,
        limit: int = 15
    ) -> List[Dict[str, Any]]:
        """
        Phân tích topics phổ biến từ conversations
        
        Args:
            min_occurrences: Số lần xuất hiện tối thiểu
            limit: Số lượng topics tối đa
            
        Returns:
            List các topics với số lần xuất hiện
        """
        try:
            # Lấy tất cả conversations
            conversations = self.db.execute(
                text("""
                    SELECT user_message, ai_response
                    FROM agent_conversations
                    WHERE user_message IS NOT NULL
                    ORDER BY created_at DESC
                    LIMIT 500
                """)
            ).fetchall()
            
            # Extract keywords (simple approach)
            all_keywords = []
            for user_msg, ai_resp in conversations:
                keywords = self._extract_keywords(user_msg)
                all_keywords.extend(keywords)
            
            # Count keywords
            keyword_counts = Counter(all_keywords)
            
            # Filter và sort
            topics = []
            for keyword, count in keyword_counts.most_common(limit * 2):
                if count >= min_occurrences and len(keyword) > 2:
                    topics.append({
                        "topic": keyword,
                        "occurrences": count,
                        "percentage": round((count / len(all_keywords)) * 100, 2) if all_keywords else 0
                    })
                    if len(topics) >= limit:
                        break
            
            return topics
        except Exception as e:
            logger.error(f"Error analyzing topics: {e}")
            return []
    
    def analyze_response_patterns(
        self,
        min_rating: int = 4,
        min_frequency: int = 2
    ) -> Dict[str, Any]:
        """
        Phân tích patterns của responses tốt và xấu
        
        Args:
            min_rating: Rating tối thiểu để coi là "tốt"
            min_frequency: Tần suất tối thiểu
            
        Returns:
            Dict với patterns tốt và xấu
        """
        try:
            # Import models (lazy import để tránh circular import)
            from models import AgentConversation, ConversationFeedback
            
            if not AgentConversation or not ConversationFeedback:
                return {
                    "good_patterns": {},
                    "bad_patterns": {},
                    "good_count": 0,
                    "bad_count": 0,
                    "insights": []
                }
            
            # Lấy conversations với feedback
            good_responses = self.db.query(
                AgentConversation.user_message,
                AgentConversation.ai_response,
                ConversationFeedback.rating
            ).join(
                ConversationFeedback,
                AgentConversation.id == ConversationFeedback.conversation_id
            ).filter(
                ConversationFeedback.rating >= min_rating
            ).all()
            
            bad_responses = self.db.query(
                AgentConversation.user_message,
                AgentConversation.ai_response,
                ConversationFeedback.rating
            ).join(
                ConversationFeedback,
                AgentConversation.id == ConversationFeedback.conversation_id
            ).filter(
                ConversationFeedback.rating < 3
            ).all()
            
            # Phân tích patterns
            good_patterns = self._analyze_response_characteristics(good_responses)
            bad_patterns = self._analyze_response_characteristics(bad_responses)
            
            return {
                "good_patterns": good_patterns,
                "bad_patterns": bad_patterns,
                "good_count": len(good_responses),
                "bad_count": len(bad_responses),
                "insights": self._generate_insights(good_patterns, bad_patterns)
            }
        except Exception as e:
            logger.error(f"Error analyzing response patterns: {e}")
            return {
                "good_patterns": {},
                "bad_patterns": {},
                "good_count": 0,
                "bad_count": 0,
                "insights": []
            }
    
    def analyze_user_intents(
        self,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Phân tích user intents từ conversations
        
        Returns:
            List các intent patterns
        """
        try:
            conversations = self.db.execute(
                text("""
                    SELECT user_message
                    FROM agent_conversations
                    WHERE user_message IS NOT NULL
                    ORDER BY created_at DESC
                    LIMIT 200
                """)
            ).fetchall()
            
            intents = defaultdict(int)
            
            # Intent keywords mapping
            intent_keywords = {
                "question": ["là gì", "gì", "như thế nào", "tại sao", "cách", "hướng dẫn"],
                "request": ["làm", "tạo", "viết", "giúp", "cho tôi", "cần"],
                "greeting": ["xin chào", "chào", "hello", "hi"],
                "thanks": ["cảm ơn", "thank", "thanks"],
                "complaint": ["sai", "không đúng", "lỗi", "vấn đề"],
                "clarification": ["ý bạn là", "nghĩa là", "có nghĩa"],
            }
            
            for (user_msg,) in conversations:
                user_msg_lower = user_msg.lower()
                for intent, keywords in intent_keywords.items():
                    if any(keyword in user_msg_lower for keyword in keywords):
                        intents[intent] += 1
                        break
            
            intent_list = [
                {
                    "intent": intent,
                    "count": count,
                    "percentage": round((count / len(conversations)) * 100, 2) if conversations else 0
                }
                for intent, count in sorted(intents.items(), key=lambda x: x[1], reverse=True)
            ]
            
            return intent_list[:limit]
        except Exception as e:
            logger.error(f"Error analyzing user intents: {e}")
            return []
    
    def find_similar_conversations(
        self,
        user_message: str,
        limit: int = 5,
        min_rating: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Tìm conversations tương tự để học từ responses tốt
        
        Args:
            user_message: Message cần tìm tương tự
            limit: Số lượng kết quả
            min_rating: Rating tối thiểu (nếu có feedback)
            
        Returns:
            List conversations tương tự
        """
        try:
            from models import AgentConversation, ConversationFeedback
            
            # Lấy keywords từ user message
            query_keywords = set(self._extract_keywords(user_message.lower()))
            
            # Lấy conversations
            query = self.db.query(AgentConversation)
            
            # Filter by rating nếu có
            if min_rating:
                query = query.join(
                    ConversationFeedback,
                    AgentConversation.id == ConversationFeedback.conversation_id
                ).filter(ConversationFeedback.rating >= min_rating)
            
            conversations = query.order_by(
                AgentConversation.created_at.desc()
            ).limit(100).all()
            
            # Tính similarity
            similar_convs = []
            for conv in conversations:
                conv_keywords = set(self._extract_keywords(conv.user_message.lower()))
                
                # Simple Jaccard similarity
                if query_keywords and conv_keywords:
                    intersection = len(query_keywords & conv_keywords)
                    union = len(query_keywords | conv_keywords)
                    similarity = intersection / union if union > 0 else 0
                    
                    if similarity > 0.2:  # Threshold
                        similar_convs.append({
                            "conversation_id": conv.id,
                            "user_message": conv.user_message,
                            "ai_response": conv.ai_response,
                            "similarity": round(similarity, 3),
                            "session_id": conv.session_id,
                            "created_at": conv.created_at.isoformat()
                        })
            
            # Sort by similarity
            similar_convs.sort(key=lambda x: x["similarity"], reverse=True)
            
            return similar_convs[:limit]
        except Exception as e:
            logger.error(f"Error finding similar conversations: {e}")
            return []
    
    def get_response_suggestions(
        self,
        user_message: str,
        use_patterns: bool = True
    ) -> Dict[str, Any]:
        """
        Đề xuất response dựa trên patterns đã học
        
        Args:
            user_message: Message từ user
            use_patterns: Có sử dụng patterns không
            
        Returns:
            Dict với suggestions và insights
        """
        try:
            suggestions = {
                "similar_conversations": [],
                "common_patterns": {},
                "recommended_approach": None
            }
            
            # Tìm similar conversations với high rating
            similar = self.find_similar_conversations(
                user_message,
                limit=3,
                min_rating=4
            )
            suggestions["similar_conversations"] = similar
            
            if use_patterns:
                # Phân tích patterns
                response_patterns = self.analyze_response_patterns(min_rating=4)
                
                if response_patterns.get("good_patterns"):
                    suggestions["common_patterns"] = {
                        "avg_length": response_patterns["good_patterns"].get("avg_length"),
                        "common_starters": response_patterns["good_patterns"].get("common_starters", [])[:3],
                        "key_phrases": response_patterns["good_patterns"].get("key_phrases", [])[:5]
                    }
                
                # Đề xuất approach
                if similar:
                    best_response = similar[0].get("ai_response", "")
                    suggestions["recommended_approach"] = {
                        "style": "similar_to_high_rated",
                        "example_response": best_response[:200] + "..." if len(best_response) > 200 else best_response
                    }
                else:
                    suggestions["recommended_approach"] = {
                        "style": "general",
                        "note": "No similar high-rated conversations found. Use general approach."
                    }
            
            return suggestions
        except Exception as e:
            logger.error(f"Error getting response suggestions: {e}")
            return {
                "similar_conversations": [],
                "common_patterns": {},
                "recommended_approach": None
            }
    
    def get_pattern_insights(self, session_id: Optional[str] = None, use_cache: bool = True) -> Dict[str, Any]:
        """
        Tổng hợp insights từ tất cả patterns với caching support
        
        Args:
            session_id: Session ID để cache (optional)
            use_cache: Có sử dụng cache không (default: True)
        
        Returns:
            Dict với tổng hợp insights
        """
        # Try to get from cache first
        if use_cache and session_id and CACHE_AVAILABLE and cache_service and cache_service.enabled:
            cached_insights = cache_service.get_cached_pattern_analysis(session_id, limit=10)
            if cached_insights:
                logger.debug(f"Cache hit for pattern insights: session {session_id}")
                return cached_insights
        
        try:
            # Analyze all patterns
            common_questions = self.analyze_common_questions(min_frequency=2, limit=10)
            topics = self.analyze_topics(min_occurrences=2, limit=10)
            intents = self.analyze_user_intents(limit=10)
            response_patterns = self.analyze_response_patterns(min_rating=4)
            
            # Get stats
            total_convs = self.db.execute(
                text("SELECT COUNT(*) FROM agent_conversations")
            ).scalar() or 0
            
            insights = {
                "total_conversations": total_convs,
                "common_questions": common_questions,
                "topics": topics,
                "user_intents": intents,
                "response_patterns": response_patterns,
                "summary": {
                    "most_common_question": common_questions[0] if common_questions else None,
                    "top_topic": topics[0] if topics else None,
                    "most_common_intent": intents[0] if intents else None,
                    "good_response_count": response_patterns.get("good_count", 0),
                    "bad_response_count": response_patterns.get("bad_count", 0)
                }
            }
            
            # Cache the result if session_id provided
            if use_cache and session_id and CACHE_AVAILABLE and cache_service and cache_service.enabled:
                cache_service.cache_pattern_analysis(session_id, insights, limit=10)
                logger.debug(f"Cached pattern insights: session {session_id}")
            
            return insights
        except Exception as e:
            logger.error(f"Error getting pattern insights: {e}")
            return {
                "error": str(e)
            }
    
    # Helper methods
    def _is_question(self, text: str) -> bool:
        """Kiểm tra xem text có phải là câu hỏi không"""
        question_indicators = ["?", "là gì", "như thế nào", "tại sao", "cách", "bao nhiêu", "khi nào", "ở đâu"]
        text_lower = text.lower()
        return any(indicator in text_lower for indicator in question_indicators)
    
    def _extract_keywords(self, text: str) -> List[str]:
        """Extract keywords từ text (simple approach)"""
        # Remove common Vietnamese stop words
        stop_words = {
            "là", "của", "và", "với", "cho", "từ", "trong", "về", "đến", "được",
            "có", "không", "một", "các", "như", "này", "đó", "nào", "đã", "sẽ",
            "the", "a", "an", "is", "are", "was", "were", "be", "been", "have",
            "has", "had", "do", "does", "did", "will", "would", "could", "should"
        }
        
        # Simple word extraction
        words = re.findall(r'\b\w+\b', text.lower())
        keywords = [w for w in words if len(w) > 2 and w not in stop_words]
        
        return keywords
    
    def _analyze_response_characteristics(
        self,
        responses: List[Tuple[str, str, int]]
    ) -> Dict[str, Any]:
        """Phân tích đặc điểm của responses"""
        if not responses:
            return {}
        
        lengths = [len(ai_resp) for _, ai_resp, _ in responses if ai_resp]
        starters = []
        all_keywords = []
        
        for _, ai_resp, _ in responses:
            if ai_resp:
                # First few words
                first_words = ai_resp.split()[:3]
                if first_words:
                    starters.append(" ".join(first_words).lower())
                
                # Keywords
                keywords = self._extract_keywords(ai_resp)
                all_keywords.extend(keywords)
        
        # Count common starters
        starter_counts = Counter(starters)
        keyword_counts = Counter(all_keywords)
        
        return {
            "avg_length": round(sum(lengths) / len(lengths), 2) if lengths else 0,
            "min_length": min(lengths) if lengths else 0,
            "max_length": max(lengths) if lengths else 0,
            "common_starters": [{"phrase": phrase, "count": count} 
                              for phrase, count in starter_counts.most_common(5)],
            "key_phrases": [{"phrase": phrase, "count": count} 
                          for phrase, count in keyword_counts.most_common(10)]
        }
    
    def _generate_insights(
        self,
        good_patterns: Dict[str, Any],
        bad_patterns: Dict[str, Any]
    ) -> List[str]:
        """Generate insights từ patterns"""
        insights = []
        
        if good_patterns and bad_patterns:
            good_avg_len = good_patterns.get("avg_length", 0)
            bad_avg_len = bad_patterns.get("avg_length", 0)
            
            if good_avg_len > 0 and bad_avg_len > 0:
                if good_avg_len > bad_avg_len * 1.5:
                    insights.append("Responses tốt thường dài hơn responses xấu")
                elif bad_avg_len > good_avg_len * 1.5:
                    insights.append("Responses xấu thường quá dài, nên ngắn gọn hơn")
            
            good_starters = [s["phrase"] for s in good_patterns.get("common_starters", [])]
            bad_starters = [s["phrase"] for s in bad_patterns.get("common_starters", [])]
            
            if good_starters:
                insights.append(f"Nên bắt đầu responses với: {', '.join(good_starters[:3])}")
        
        return insights