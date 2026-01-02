"""
Repository for ConversationEmbedding model.
Handles all database operations for embeddings.
"""
from typing import Optional, List
from sqlalchemy.orm import Session

from .base_repository import BaseRepository
from config.models import ConversationEmbedding

logger = None  # Will be initialized in __init__


class EmbeddingRepository(BaseRepository[ConversationEmbedding]):
    """Repository for ConversationEmbedding operations"""
    
    def __init__(self, session: Session):
        super().__init__(session, ConversationEmbedding)
        global logger
        import logging
        logger = logging.getLogger(__name__)
    
    def get_by_conversation_id(self, conversation_id: int) -> Optional[ConversationEmbedding]:
        """Get embedding by conversation ID"""
        return (
            self.session.query(self.model)
            .filter(self.model.conversation_id == conversation_id)
            .first()
        )
    
    def upsert_embedding(
        self,
        conversation_id: int,
        user_message_embedding: Optional[str] = None,
        ai_response_embedding: Optional[str] = None,
        combined_embedding: Optional[str] = None,
        embedding_model: str = "sentence-transformers",
        embedding_dimension: int = 384
    ) -> ConversationEmbedding:
        """Create or update embedding for a conversation"""
        existing = self.get_by_conversation_id(conversation_id)
        
        if existing:
            update_data = {}
            if user_message_embedding is not None:
                update_data["user_message_embedding"] = user_message_embedding
            if ai_response_embedding is not None:
                update_data["ai_response_embedding"] = ai_response_embedding
            if combined_embedding is not None:
                update_data["combined_embedding"] = combined_embedding
            if embedding_model:
                update_data["embedding_model"] = embedding_model
            if embedding_dimension:
                update_data["embedding_dimension"] = embedding_dimension
            
            updated = self.update(existing.id, **update_data)
            return updated if updated else existing
        else:
            return self.create(
                conversation_id=conversation_id,
                user_message_embedding=user_message_embedding,
                ai_response_embedding=ai_response_embedding,
                combined_embedding=combined_embedding,
                embedding_model=embedding_model,
                embedding_dimension=embedding_dimension
            )