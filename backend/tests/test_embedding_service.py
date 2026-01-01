"""
Tests cho Embedding Service
"""
import pytest
from unittest.mock import patch, MagicMock
from services.embedding_service import EmbeddingService


def test_embedding_service_initialization():
    """Test Embedding service initialization"""
    service = EmbeddingService()
    assert service is not None
    assert service.embedding_provider in ["sentence-transformers", "ollama"]


@pytest.mark.asyncio
async def test_generate_embedding():
    """Test generate embedding"""
    service = EmbeddingService()
    
    # Mock sentence-transformers
    with patch("services.embedding_service.SentenceTransformer") as mock_st:
        mock_model = MagicMock()
        mock_model.encode.return_value = [0.1] * 384  # Mock embedding vector
        mock_st.return_value = mock_model
        
        embedding = await service.generate_embedding("Hello world")
        assert embedding is not None
        assert isinstance(embedding, list)
        assert len(embedding) == 384


@pytest.mark.asyncio
async def test_generate_embedding_with_cache():
    """Test generate embedding với cache"""
    service = EmbeddingService()
    
    # Mock cache service với cache hit
    with patch("services.embedding_service.cache_service") as mock_cache:
        mock_cache.enabled = True
        mock_cache.get_cached_embedding.return_value = [0.1] * 384
        
        embedding = await service.generate_embedding("Hello world")
        assert embedding is not None
        assert len(embedding) == 384


@pytest.mark.asyncio
async def test_generate_embedding_empty_text():
    """Test generate embedding với empty text"""
    service = EmbeddingService()
    
    embedding = await service.generate_embedding("")
    assert embedding is None
    
    embedding = await service.generate_embedding("   ")
    assert embedding is None