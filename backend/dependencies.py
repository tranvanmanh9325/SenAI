"""
Dependency Injection module for FastAPI.
Provides dependency functions for injecting services, repositories, and other dependencies.
This module helps avoid circular imports and enables proper dependency injection.
"""
from typing import Iterator
from collections.abc import AsyncIterator
from fastapi import Depends
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession

# Import database session factories
from config.app_config import SessionLocal, AsyncSessionLocal

# Import repositories
from repositories import (
    TaskRepository,
    ConversationRepository,
    FeedbackRepository,
    EmbeddingRepository,
    APIKeyRepository,
    CacheRepository,
)
from repositories.api_key_repository import APIKeyAuditLogRepository

# Import services - lazy import to avoid circular dependencies
# Services will be imported when needed in service factory functions


# Database session dependencies
def get_db() -> Iterator[Session]:
    """Dependency to get database session (sync)"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


async def get_async_db() -> AsyncIterator[AsyncSession]:
    """Dependency to get async database session"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


# Repository dependencies
def get_task_repository(db: Session = Depends(get_db)) -> TaskRepository:
    """Dependency to get TaskRepository"""
    return TaskRepository(db)


def get_conversation_repository(db: Session = Depends(get_db)) -> ConversationRepository:
    """Dependency to get ConversationRepository"""
    return ConversationRepository(db)


def get_feedback_repository(db: Session = Depends(get_db)) -> FeedbackRepository:
    """Dependency to get FeedbackRepository"""
    return FeedbackRepository(db)


def get_embedding_repository(db: Session = Depends(get_db)) -> EmbeddingRepository:
    """Dependency to get EmbeddingRepository"""
    return EmbeddingRepository(db)


def get_api_key_repository(db: Session = Depends(get_db)) -> APIKeyRepository:
    """Dependency to get APIKeyRepository"""
    return APIKeyRepository(db)


def get_api_key_audit_log_repository(db: Session = Depends(get_db)) -> APIKeyAuditLogRepository:
    """Dependency to get APIKeyAuditLogRepository"""
    return APIKeyAuditLogRepository(db)


def get_cache_repository(db: Session = Depends(get_db)) -> CacheRepository:
    """Dependency to get CacheRepository"""
    return CacheRepository(db)


# Service factory functions (lazy imports to avoid circular dependencies)
def get_llm_service():
    """Dependency to get LLMService instance"""
    from factories.llm_factory import create_llm_service
    return create_llm_service()


def get_feedback_service(
    feedback_repo: FeedbackRepository = Depends(get_feedback_repository),
    conversation_repo: ConversationRepository = Depends(get_conversation_repository)
):
    """Dependency to get FeedbackService instance"""
    from services.feedback_service import FeedbackService
    return FeedbackService(feedback_repository=feedback_repo, conversation_repository=conversation_repo)


def get_embedding_service(
    embedding_repo: EmbeddingRepository = Depends(get_embedding_repository),
    conversation_repo: ConversationRepository = Depends(get_conversation_repository)
):
    """Dependency to get EmbeddingService instance"""
    from services.embedding_service import EmbeddingService
    # Note: EmbeddingService might need additional dependencies
    # This will need to be adjusted based on actual EmbeddingService implementation
    # For now, keep backward compatibility - EmbeddingService may still use db directly
    return EmbeddingService(embedding_repo, conversation_repo)