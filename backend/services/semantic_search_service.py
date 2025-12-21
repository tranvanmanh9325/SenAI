"""
Semantic Search Service để tìm kiếm ngữ nghĩa
Sử dụng embeddings để tìm conversations tương tự
Hỗ trợ cả JSON text storage và pgvector
"""
import json
import logging
import os
from typing import List, Dict, Any, Optional, Tuple
import numpy as np
from sqlalchemy.orm import Session
from sqlalchemy import text

from .embedding_service import embedding_service

logger = logging.getLogger(__name__)

# Check if pgvector is enabled
USE_PGVECTOR = os.getenv("USE_PGVECTOR", "false").lower() == "true"

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
        filter_by_rating: Optional[int] = None,
        max_candidates: int = 1000  # Giới hạn số lượng embeddings được so sánh
    ) -> List[Dict[str, Any]]:
        """
        Tìm conversations tương tự bằng semantic search
        Tối ưu để không load tất cả embeddings vào memory
        
        Args:
            query_text: Text cần tìm
            limit: Số lượng kết quả tối đa
            min_similarity: Độ tương tự tối thiểu (0-1)
            use_combined: Sử dụng combined embedding không
            filter_by_rating: Filter theo rating tối thiểu (nếu có feedback)
            max_candidates: Số lượng embeddings tối đa để so sánh (để tránh load quá nhiều vào memory)
            
        Returns:
            List conversations tương tự với similarity scores
        """
        try:
            # Generate query embedding
            query_embedding = await embedding_service.generate_embedding(query_text)
            if not query_embedding:
                logger.error("Failed to generate query embedding")
                return []
            
            query_vec = np.array(query_embedding)
            
            # Kiểm tra xem có thể sử dụng pgvector không
            if USE_PGVECTOR:
                try:
                    # Kiểm tra xem vector columns có tồn tại không
                    check_sql = """
                        SELECT column_name 
                        FROM information_schema.columns 
                        WHERE table_name = 'conversation_embeddings' 
                        AND column_name = 'combined_embedding_vector'
                    """
                    result = self.db.execute(text(check_sql)).fetchone()
                    
                    if result:
                        # Sử dụng pgvector với cosine similarity
                        return await self._search_with_pgvector(
                            query_vec, limit, min_similarity, use_combined, 
                            filter_by_rating, max_candidates
                        )
                except Exception as e:
                    logger.warning(f"pgvector search failed, falling back to JSON: {e}")
            
            # Fallback: Sử dụng JSON text storage với batch processing
            return await self._search_with_json(
                query_vec, limit, min_similarity, use_combined, 
                filter_by_rating, max_candidates
            )
            
        except Exception as e:
            logger.error(f"Error in semantic search: {e}")
            return []
    
    async def _search_with_pgvector(
        self,
        query_vec: np.ndarray,
        limit: int,
        min_similarity: float,
        use_combined: bool,
        filter_by_rating: Optional[int],
        max_candidates: int
    ) -> List[Dict[str, Any]]:
        """Search sử dụng pgvector với native vector operations"""
        try:
            # Convert query vector to PostgreSQL array format
            query_vec_str = "[" + ",".join(map(str, query_vec)) + "]"
            
            # Chọn cột vector để search
            vector_column = "combined_embedding_vector" if use_combined else "user_message_embedding_vector"
            
            # Build query với pgvector cosine similarity
            query_sql = f"""
                SELECT 
                    ce.conversation_id,
                    ac.user_message,
                    ac.ai_response,
                    ac.session_id,
                    ac.created_at,
                    1 - (ce.{vector_column} <=> :query_vec::vector) as similarity
                FROM conversation_embeddings ce
                JOIN agent_conversations ac ON ce.conversation_id = ac.id
            """
            
            # Add rating filter nếu có
            if filter_by_rating:
                query_sql += """
                    JOIN conversation_feedback cf ON ce.conversation_id = cf.conversation_id
                    WHERE ce.{vector_column} IS NOT NULL AND cf.rating >= :min_rating
                """.format(vector_column=vector_column)
            else:
                query_sql += f" WHERE ce.{vector_column} IS NOT NULL"
            
            # Order by similarity DESC và limit
            query_sql += f" ORDER BY ce.{vector_column} <=> :query_vec::vector LIMIT :result_limit"
            
            params = {
                "query_vec": query_vec_str,
                "result_limit": limit,
                "min_similarity": min_similarity
            }
            if filter_by_rating:
                params["min_rating"] = filter_by_rating
            
            results = self.db.execute(text(query_sql), params).fetchall()
            
            similarities = []
            for row in results:
                conv_id, user_msg, ai_resp, session_id, created_at, similarity = row
                
                if similarity >= min_similarity:
                    similarities.append({
                        "conversation_id": conv_id,
                        "user_message": user_msg,
                        "ai_response": ai_resp,
                        "similarity": round(float(similarity), 4),
                        "session_id": session_id,
                        "created_at": created_at.isoformat() if created_at else None
                    })
            
            return similarities
            
        except Exception as e:
            logger.error(f"Error in pgvector search: {e}")
            raise
    
    async def _search_with_json(
        self,
        query_vec: np.ndarray,
        limit: int,
        min_similarity: float,
        use_combined: bool,
        filter_by_rating: Optional[int],
        max_candidates: int
    ) -> List[Dict[str, Any]]:
        """Search sử dụng JSON text storage với batch processing"""
        # Xây dựng query với limit để không load tất cả embeddings
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
        
        # Order by created_at DESC để ưu tiên conversations mới nhất
        query_sql += f" ORDER BY ac.created_at DESC LIMIT :max_candidates"
        
        params = {"max_candidates": max_candidates}
        if filter_by_rating:
            params["min_rating"] = filter_by_rating
        
        # Batch processing: xử lý từng batch nhỏ để tiết kiệm memory
        batch_size = 100
        similarities = []
        processed = 0
        
        # Lấy embeddings theo batch
        for offset in range(0, max_candidates, batch_size):
            batch_query = query_sql.replace("LIMIT :max_candidates", f"LIMIT {batch_size} OFFSET {offset}")
            batch_params = {k: v for k, v in params.items() if k != "max_candidates"}
            
            embeddings_batch = self.db.execute(text(batch_query), batch_params).fetchall()
            
            if not embeddings_batch:
                break
            
            # Xử lý batch này
            for row in embeddings_batch:
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
                        
                        # Early termination: nếu đã có đủ kết quả với similarity cao, có thể dừng sớm
                        if len(similarities) >= limit * 2 and min(s["similarity"] for s in similarities) > min_similarity + 0.2:
                            break
                except Exception as e:
                    logger.warning(f"Error processing embedding for conversation {conv_id}: {e}")
                    continue
            
            processed += len(embeddings_batch)
            
            # Early termination nếu đã có đủ kết quả tốt
            if len(similarities) >= limit * 2:
                break
        
        # Sort by similarity và trả về top results
        similarities.sort(key=lambda x: x["similarity"], reverse=True)
        
        logger.debug(f"Processed {processed} embeddings, found {len(similarities)} similar conversations")
        
        return similarities[:limit]
    
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
            from models import ConversationEmbedding
            
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
            
            # Convert embeddings to formats
            user_emb_json = json.dumps(embeddings["user_message_embedding"])
            ai_emb_json = json.dumps(embeddings["ai_response_embedding"]) if embeddings.get("ai_response_embedding") else None
            combined_emb_json = json.dumps(embeddings["combined_embedding"])
            
            # Convert to vector format nếu sử dụng pgvector
            user_emb_vec = None
            ai_emb_vec = None
            combined_emb_vec = None
            
            if USE_PGVECTOR:
                try:
                    # Check if vector columns exist
                    check_sql = """
                        SELECT column_name 
                        FROM information_schema.columns 
                        WHERE table_name = 'conversation_embeddings' 
                        AND column_name = 'combined_embedding_vector'
                    """
                    result = self.db.execute(text(check_sql)).fetchone()
                    
                    if result:
                        # Convert to PostgreSQL array format
                        user_emb_vec = "[" + ",".join(map(str, embeddings["user_message_embedding"])) + "]"
                        if embeddings.get("ai_response_embedding"):
                            ai_emb_vec = "[" + ",".join(map(str, embeddings["ai_response_embedding"])) + "]"
                        combined_emb_vec = "[" + ",".join(map(str, embeddings["combined_embedding"])) + "]"
                except Exception as e:
                    logger.warning(f"Failed to prepare vector format: {e}")
            
            if existing:
                # Update existing
                existing.user_message_embedding = user_emb_json
                existing.ai_response_embedding = ai_emb_json
                existing.combined_embedding = combined_emb_json
                existing.embedding_model = embeddings["embedding_model"]
                existing.embedding_dimension = embeddings.get("dimension", 384)
                
                # Update vector columns nếu có
                if combined_emb_vec:
                    try:
                        update_vec_sql = """
                            UPDATE conversation_embeddings
                            SET combined_embedding_vector = :combined_vec::vector
                        """
                        params = {"combined_vec": combined_emb_vec, "id": existing.id}
                        
                        if user_emb_vec:
                            update_vec_sql += ", user_message_embedding_vector = :user_vec::vector"
                            params["user_vec"] = user_emb_vec
                        
                        if ai_emb_vec:
                            update_vec_sql += ", ai_response_embedding_vector = :ai_vec::vector"
                            params["ai_vec"] = ai_emb_vec
                        
                        update_vec_sql += " WHERE id = :id"
                        self.db.execute(text(update_vec_sql), params)
                    except Exception as e:
                        logger.warning(f"Failed to update vector columns: {e}")
                
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
                    user_message_embedding=user_emb_json,
                    ai_response_embedding=ai_emb_json,
                    combined_embedding=combined_emb_json,
                    embedding_model=embeddings["embedding_model"],
                    embedding_dimension=embeddings.get("dimension", 384)
                )
                
                self.db.add(embedding_record)
                self.db.flush()  # Get the ID
                
                # Insert vector columns nếu có
                if combined_emb_vec:
                    try:
                        insert_vec_sql = """
                            UPDATE conversation_embeddings
                            SET combined_embedding_vector = :combined_vec::vector
                        """
                        params = {"combined_vec": combined_emb_vec, "id": embedding_record.id}
                        
                        if user_emb_vec:
                            insert_vec_sql += ", user_message_embedding_vector = :user_vec::vector"
                            params["user_vec"] = user_emb_vec
                        
                        if ai_emb_vec:
                            insert_vec_sql += ", ai_response_embedding_vector = :ai_vec::vector"
                            params["ai_vec"] = ai_emb_vec
                        
                        insert_vec_sql += " WHERE id = :id"
                        self.db.execute(text(insert_vec_sql), params)
                    except Exception as e:
                        logger.warning(f"Failed to insert vector columns: {e}")
                
                self.db.commit()
                
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