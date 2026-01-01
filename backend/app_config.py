"""
App Config module - Backward compatibility wrapper
Re-exports from config.app_config to maintain compatibility
"""
from config.app_config import (
    # Database
    SessionLocal,
    AsyncSessionLocal,
    engine,
    async_engine,
    
    # Configuration
    ALLOWED_ORIGINS,
    
    # Functions
    lifespan,
    setup_database_indexes,
    
    # Models (Pydantic)
    TaskCreate,
    TaskResponse,
    ConversationCreate,
    ConversationResponse,
    FeedbackCreate,
    FeedbackResponse,
    FeedbackStats,
)

__all__ = [
    "SessionLocal",
    "AsyncSessionLocal",
    "engine",
    "async_engine",
    "ALLOWED_ORIGINS",
    "lifespan",
    "setup_database_indexes",
    "TaskCreate",
    "TaskResponse",
    "ConversationCreate",
    "ConversationResponse",
    "FeedbackCreate",
    "FeedbackResponse",
    "FeedbackStats",
]
