"""
Database Models
Tách riêng models để tránh circular imports
"""
from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean, ForeignKey, Index
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
    __table_args__ = (
        # Indexes để optimize queries thường dùng
        Index('idx_agent_conversations_session_id', 'session_id'),
        Index('idx_agent_conversations_created_at', 'created_at'),
        Index('idx_agent_conversations_session_created', 'session_id', 'created_at'),
    )
    
    id: int = Column(Integer, primary_key=True, index=True)
    user_message: str = Column(Text, nullable=False)
    ai_response: str | None = Column(Text, nullable=True)
    session_id: str | None = Column(String(255), nullable=True)
    created_at: datetime = Column(DateTime, default=datetime.utcnow)


class ConversationFeedback(Base):
    """Model cho conversation feedback"""
    __tablename__ = "conversation_feedback"
    __table_args__ = (
        # Indexes để optimize queries thường dùng
        Index('idx_conversation_feedback_conversation_id', 'conversation_id'),
        Index('idx_conversation_feedback_rating', 'rating'),
        Index('idx_conversation_feedback_conv_rating', 'conversation_id', 'rating'),
    )
    
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
    __table_args__ = (
        # Index để optimize queries thường dùng
        Index('idx_conversation_embeddings_conversation_id', 'conversation_id'),
    )
    
    id: int = Column(Integer, primary_key=True, index=True)
    conversation_id: int = Column(Integer, nullable=False, unique=True, index=True)
    
    # Embedding columns - JSON text storage (luôn có để backward compatibility)
    # Note: pgvector columns sẽ được thêm bằng migration script nếu cần
    # Các cột vector: combined_embedding_vector, user_message_embedding_vector, ai_response_embedding_vector
    user_message_embedding: str | None = Column(Text, nullable=True)  # JSON array của embedding vector
    ai_response_embedding: str | None = Column(Text, nullable=True)  # JSON array của embedding vector
    combined_embedding: str | None = Column(Text, nullable=True)  # JSON array của combined embedding
    
    # pgvector columns (nếu enabled)
    # Note: Các cột vector này chỉ được tạo khi USE_PGVECTOR=true và pgvector extension được cài đặt
    # Sử dụng user_message_embedding, ai_response_embedding, combined_embedding cho JSON storage
    if USE_PGVECTOR and PGVECTOR_AVAILABLE and Vector:
        user_message_embedding_vector = Column(Vector(384), nullable=True)
        ai_response_embedding_vector = Column(Vector(384), nullable=True)
        combined_embedding_vector = Column(Vector(384), nullable=True)
    
    embedding_model: str = Column(String(100), default="sentence-transformers")  # Model đã dùng
    embedding_dimension: int = Column(Integer, default=384)  # Dimension của embedding
    created_at: datetime = Column(DateTime, default=datetime.utcnow)
    updated_at: datetime = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class APIKey(Base):
    """
    Model cho API keys dùng cho authentication & authorization.
    Chỉ lưu hash của key, không bao giờ lưu plain text key.
    """

    __tablename__ = "api_keys"

    id: int = Column(Integer, primary_key=True, index=True)
    # SHA-256 hex hash của API key
    key_hash: str = Column(String(64), unique=True, nullable=False, index=True)

    # Thông tin mô tả và gán cho user (nếu có)
    name: str = Column(String(255), nullable=False)
    user_id: int | None = Column(Integer, nullable=True, index=True)

    # Permissions được lưu dạng JSON string (["read", "write", "admin"])
    permissions: str | None = Column(Text, nullable=True)

    # Rate limit riêng cho key này (vd: "100/minute")
    rate_limit: str = Column(String(50), default="100/minute")

    # Quản lý vòng đời key
    created_at: datetime = Column(DateTime, default=datetime.utcnow)
    expires_at: datetime | None = Column(DateTime, nullable=True)
    last_used_at: datetime | None = Column(DateTime, nullable=True)

    # Trạng thái hoạt động
    is_active: bool = Column(Boolean, default=True, index=True)


class APIKeyAuditLog(Base):
    """
    Audit log cho việc sử dụng API key.
    Ghi lại mỗi request: endpoint, method, IP, user-agent, status code, thời gian phản hồi.
    """

    __tablename__ = "api_key_audit_logs"

    id: int = Column(Integer, primary_key=True, index=True)

    api_key_id: int = Column(
        Integer,
        ForeignKey("api_keys.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    endpoint: str = Column(String(512), nullable=False)
    method: str = Column(String(10), nullable=False)
    ip_address: str | None = Column(String(64), nullable=True)
    user_agent: str | None = Column(Text, nullable=True)

    status_code: int = Column(Integer, nullable=False)
    response_time_ms: int | None = Column(Integer, nullable=True)

    created_at: datetime = Column(DateTime, default=datetime.utcnow, index=True)


class CacheEntry(Base):
    """
    Model cho L3 cache (persistent database cache)
    Lưu trữ cache entries với metadata để hỗ trợ adaptive TTL và cache warming
    """
    __tablename__ = "cache_entries"
    __table_args__ = (
        Index('idx_cache_entries_key', 'cache_key'),
        Index('idx_cache_entries_type', 'cache_type'),
        Index('idx_cache_entries_expires', 'expires_at'),
        Index('idx_cache_entries_access_count', 'access_count'),
        Index('idx_cache_entries_last_accessed', 'last_accessed'),
    )
    
    id: int = Column(Integer, primary_key=True, index=True)
    cache_key: str = Column(String(512), unique=True, nullable=False, index=True)
    cache_value: str = Column(Text, nullable=False)  # JSON string
    cache_type: str = Column(String(50), nullable=False, index=True)  # embedding, llm, pattern_analysis, etc.
    
    # TTL và expiration
    expires_at: datetime = Column(DateTime, nullable=False, index=True)
    created_at: datetime = Column(DateTime, default=datetime.utcnow)
    
    # Access pattern tracking for adaptive TTL
    access_count: int = Column(Integer, default=0, index=True)
    last_accessed: datetime = Column(DateTime, default=datetime.utcnow, index=True)