"""
Semantic Search Service để tìm kiếm ngữ nghĩa
Sử dụng embeddings để tìm conversations tương tự
"""
import json
import logging
from typing import List, Dict, Any, Optional, Tuple
import numpy as np
from sqlalchemy.orm import Session
from sqlalchemy import text

from embedding_service import embedding_service

logger = logging.getLogger(__name__)

class SemanticSearchService:
    """Service để tìm kiếm ngữ nghĩa sử dụng embeddings"""
    
    def __init__(self, db: Session):
        self.db = db
    
    async def search_similar_conversations(
        self,
        query_text: str,
        limit: int = 5,
        min_similarity: float = 0.5,
        use_combined: bool = True,
        filter_by_rating: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Tìm conversations tương tự bằng semantic search
        
        Args:
            query_text: Text cần tìm
            limit: Số lượng kết quả tối đa
            min_similarity: Độ tương tự tối thiểu (0-1)
            use_combined: Sử dụng combined embedding không
            filter_by_rating: Filter theo rating tối thiểu (nếu có feedback)
            
        Returns:
            List conversations tương tự với similarity scores
        """
        try:
            # Generate query embedding
            query_embedding = await embedding_service.generate_embedding(query_text)
            if not query_embedding:
                logger.error("Failed to generate query embedding")
                return []
            
            # Lấy tất cả embeddings từ database
            query_sql = """
                SELECT 
                    ce.conversation_id,
                    ce.user_message_embedding,
                    ce.ai_response_embedding,
                    ce.combined_embedding,
                    ce.embedding_dimension,
                    ac.user_message,
                    ac.ai_response,
                    ac.session_id,
                    ac.created_at
                FROM conversation_embeddings ce
                JOIN agent_conversations ac ON ce.conversation_id = ac.id
            """
            
            # Add rating filter nếu có
            if filter_by_rating:
                query_sql += """
                    JOIN conversation_feedback cf ON ce.conversation_id = cf.conversation_id
                    WHERE cf.rating >= :min_rating
                """
            else:
                query_sql += " WHERE 1=1"
            
            params = {}
            if filter_by_rating:
                params["min_rating"] = filter_by_rating
            
            embeddings_data = self.db.execute(text(query_sql), params).fetchall()
            
            if not embeddings_data:
                return []
            
            # Tính similarity với mỗi embedding
            similarities = []
            query_vec = np.array(query_embedding)
            
            for row in embeddings_data:
                conv_id, user_emb_str, ai_emb_str, combined_emb_str, dim, user_msg, ai_resp, session_id, created_at = row
                
                # Chọn embedding để so sánh
                if use_combined and combined_emb_str:
                    target_embedding_str = combined_emb_str
                elif user_emb_str:
                    target_embedding_str = user_emb_str
                else:
                    continue
                
                try:
                    # Parse embedding từ JSON
                    target_embedding = json.loads(target_embedding_str)
                    target_vec = np.array(target_embedding)
                    
                    # Tính cosine similarity
                    similarity = self._cosine_similarity(query_vec, target_vec)
                    
                    if similarity >= min_similarity:
                        similarities.append({
                            "conversation_id": conv_id,
                            "user_message": user_msg,
                            "ai_response": ai_resp,
                            "similarity": round(float(similarity), 4),
                            "session_id": session_id,
                            "created_at": created_at.isoformat() if created_at else None
                        })
                except Exception as e:
                    logger.warning(f"Error processing embedding for conversation {conv_id}: {e}")
                    continue
            
            # Sort by similarity
            similarities.sort(key=lambda x: x["similarity"], reverse=True)
            
            return similarities[:limit]
        except Exception as e:
            logger.error(f"Error in semantic search: {e}")
            return []
    
    async def find_best_response(
        self,
        user_message: str,
        limit: int = 3,
        min_similarity: float = 0.6
    ) -> Optional[Dict[str, Any]]:
        """
        Tìm best response cho user message dựa trên semantic search
        
        Args:
            user_message: Message từ user
            limit: Số lượng candidates
            min_similarity: Độ tương tự tối thiểu
            
        Returns:
            Best response hoặc None
        """
        try:
            # Tìm similar conversations với high rating
            similar = await self.search_similar_conversations(
                query_text=user_message,
                limit=limit,
                min_similarity=min_similarity,
                filter_by_rating=4  # Chỉ lấy high-rated
            )
            
            if similar:
                # Lấy best match
                best = similar[0]
                return {
                    "conversation_id": best["conversation_id"],
                    "similar_user_message": best["user_message"],
                    "suggested_response": best["ai_response"],
                    "similarity": best["similarity"],
                    "confidence": "high" if best["similarity"] > 0.8 else "medium"
                }
            
            return None
        except Exception as e:
            logger.error(f"Error finding best response: {e}")
            return None
    
    async def get_semantic_context(
        self,
        user_message: str,
        context_limit: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Lấy semantic context (similar conversations) để cải thiện response
        
        Args:
            user_message: Message từ user
            context_limit: Số lượng context conversations
            
        Returns:
            List context conversations
        """
        try:
            similar = await self.search_similar_conversations(
                query_text=user_message,
                limit=context_limit,
                min_similarity=0.5,
                filter_by_rating=3  # Lấy cả medium-rated
            )
            
            return similar
        except Exception as e:
            logger.error(f"Error getting semantic context: {e}")
            return []
    
    def _cosine_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """Tính cosine similarity giữa 2 vectors"""
        try:
            # Normalize vectors
            vec1_norm = vec1 / (np.linalg.norm(vec1) + 1e-8)
            vec2_norm = vec2 / (np.linalg.norm(vec2) + 1e-8)
            
            # Cosine similarity
            similarity = np.dot(vec1_norm, vec2_norm)
            
            # Ensure trong range [0, 1]
            return max(0.0, min(1.0, float(similarity)))
        except Exception as e:
            logger.error(f"Error calculating cosine similarity: {e}")
            return 0.0
    
    async def index_conversation(
        self,
        conversation_id: int,
        user_message: str,
        ai_response: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Index conversation (tạo và lưu embeddings)
        
        Args:
            conversation_id: ID của conversation
            user_message: User message
            ai_response: AI response
            
        Returns:
            Dict với kết quả indexing
        """
        try:
            from app import ConversationEmbedding
            
            # Generate embeddings
            embeddings = await embedding_service.generate_conversation_embeddings(
                user_message=user_message,
                ai_response=ai_response
            )
            
            if not embeddings.get("combined_embedding"):
                return {
                    "success": False,
                    "error": "Failed to generate embeddings"
                }
            
            # Check if embedding already exists
            existing = self.db.query(ConversationEmbedding).filter(
                ConversationEmbedding.conversation_id == conversation_id
            ).first()
            
            if existing:
                # Update existing
                existing.user_message_embedding = json.dumps(embeddings["user_message_embedding"])
                existing.ai_response_embedding = json.dumps(embeddings["ai_response_embedding"]) if embeddings.get("ai_response_embedding") else None
                existing.combined_embedding = json.dumps(embeddings["combined_embedding"])
                existing.embedding_model = embeddings["embedding_model"]
                existing.embedding_dimension = embeddings.get("dimension", 384)
                
                self.db.commit()
                return {
                    "success": True,
                    "message": "Embedding updated",
                    "conversation_id": conversation_id
                }
            else:
                # Create new
                embedding_record = ConversationEmbedding(
                    conversation_id=conversation_id,
                    user_message_embedding=json.dumps(embeddings["user_message_embedding"]),
                    ai_response_embedding=json.dumps(embeddings["ai_response_embedding"]) if embeddings.get("ai_response_embedding") else None,
                    combined_embedding=json.dumps(embeddings["combined_embedding"]),
                    embedding_model=embeddings["embedding_model"],
                    embedding_dimension=embeddings.get("dimension", 384)
                )
                
                self.db.add(embedding_record)
                self.db.commit()
                
                return {
                    "success": True,
                    "message": "Embedding created",
                    "conversation_id": conversation_id
                }
        except Exception as e:
            logger.error(f"Error indexing conversation: {e}")
            self.db.rollback()
            return {
                "success": False,
                "error": str(e)
            }
    
    def get_indexing_stats(self) -> Dict[str, Any]:
        """Lấy thống kê về indexing"""
        try:
            total_convs = self.db.execute(
                text("SELECT COUNT(*) FROM agent_conversations")
            ).scalar() or 0
            
            indexed_convs = self.db.execute(
                text("SELECT COUNT(*) FROM conversation_embeddings")
            ).scalar() or 0
            
            return {
                "total_conversations": total_convs,
                "indexed_conversations": indexed_convs,
                "indexing_percentage": round((indexed_convs / total_convs * 100), 2) if total_convs > 0 else 0,
                "pending_indexing": max(0, total_convs - indexed_convs)
            }
        except Exception as e:
            logger.error(f"Error getting indexing stats: {e}")
            return {
                "error": str(e)
            }