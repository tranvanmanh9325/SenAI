"""
Database Models
Tách riêng models để tránh circular imports
"""
from sqlalchemy import Column, Integer, String, DateTime, Text
from sqlalchemy.orm import declarative_base
from datetime import datetime
import os

# Check if pgvector is available
USE_PGVECTOR = os.getenv("USE_PGVECTOR", "false").lower() == "true"
try:
    from pgvector.sqlalchemy import Vector
    PGVECTOR_AVAILABLE = True
except ImportError:
    PGVECTOR_AVAILABLE = False
    Vector = None

# Base class for models
Base = declarative_base()


class AgentTask(Base):
    """Model cho agent tasks"""
    __tablename__ = "agent_tasks"
    
    id: int = Column(Integer, primary_key=True, index=True)
    task_name: str = Column(String(255), nullable=False)
    description: str | None = Column(Text, nullable=True)
    status: str = Column(String(50), default="pending")
    result: str | None = Column(Text, nullable=True)
    created_at: datetime = Column(DateTime, default=datetime.utcnow)
    updated_at: datetime = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AgentConversation(Base):
    """Model cho agent conversations"""
    __tablename__ = "agent_conversations"
    
    id: int = Column(Integer, primary_key=True, index=True)
    user_message: str = Column(Text, nullable=False)
    ai_response: str | None = Column(Text, nullable=True)
    session_id: str | None = Column(String(255), nullable=True)
    created_at: datetime = Column(DateTime, default=datetime.utcnow)


class ConversationFeedback(Base):
    """Model cho conversation feedback"""
    __tablename__ = "conversation_feedback"
    
    id: int = Column(Integer, primary_key=True, index=True)
    conversation_id: int = Column(Integer, nullable=False, index=True)
    rating: int = Column(Integer, nullable=False)  # 1-5 stars, hoặc -1 (thumbs down), 1 (thumbs up)
    feedback_type: str = Column(String(50), default="rating")  # rating, thumbs_up, thumbs_down, detailed
    comment: str | None = Column(Text, nullable=True)  # Comment chi tiết từ user
    user_correction: str | None = Column(Text, nullable=True)  # Câu trả lời đúng nếu user sửa
    is_helpful: str | None = Column(String(10), nullable=True)  # yes, no, partially
    created_at: datetime = Column(DateTime, default=datetime.utcnow)
    updated_at: datetime = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ConversationEmbedding(Base):
    """Model cho conversation embeddings"""
    __tablename__ = "conversation_embeddings"
    
    id: int = Column(Integer, primary_key=True, index=True)
    conversation_id: int = Column(Integer, nullable=False, unique=True, index=True)
    
    # Embedding columns - JSON text storage (luôn có để backward compatibility)
    # Note: pgvector columns sẽ được thêm bằng migration script nếu cần
    # Các cột vector: combined_embedding_vector, user_message_embedding_vector, ai_response_embedding_vector
    user_message_embedding: str | None = Column(Text, nullable=True)  # JSON array của embedding vector
    ai_response_embedding: str | None = Column(Text, nullable=True)  # JSON array của embedding vector
    combined_embedding: str | None = Column(Text, nullable=True)  # JSON array của combined embedding
    
    # pgvector columns (nếu enabled)
    if USE_PGVECTOR and PGVECTOR_AVAILABLE and Vector:
        user_message_embedding_vector = Column(Vector(384), nullable=True)
        ai_response_embedding_vector = Column(Vector(384), nullable=True)
        combined_embedding_vector = Column(Vector(384), nullable=True)
        # Keep JSON columns for backward compatibility during migration
        user_message_embedding_json = Column(Text, nullable=True)
        ai_response_embedding_json = Column(Text, nullable=True)
        combined_embedding_json = Column(Text, nullable=True)
    
    embedding_model: str = Column(String(100), default="sentence-transformers")  # Model đã dùng
    embedding_dimension: int = Column(Integer, default=384)  # Dimension của embedding
    created_at: datetime = Column(DateTime, default=datetime.utcnow)
    updated_at: datetime = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

