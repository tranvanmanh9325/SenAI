"""
Tests cho LLM Service
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from services.llm_service import LLMService


@pytest.mark.asyncio
async def test_llm_service_initialization():
    """Test LLM service initialization"""
    service = LLMService()
    assert service is not None
    assert service.provider in ["ollama", "openai", "anthropic"]


@pytest.mark.asyncio
async def test_generate_response_with_mock():
    """Test generate_response với mock"""
    service = LLMService()
    
    # Mock httpx client
    with patch("services.llm_service.httpx.AsyncClient") as mock_client:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "response": "Hello! How can I help you?"
        }
        
        mock_client_instance = AsyncMock()
        mock_client_instance.post.return_value = mock_response
        mock_client.return_value.__aenter__.return_value = mock_client_instance
        
        # Mock cache service
        with patch("services.llm_service.cache_service") as mock_cache:
            mock_cache.enabled = False
            
            # Test với Ollama provider
            if service.provider == "ollama":
                with patch("services.llm_service.httpx.AsyncClient") as mock_ollama:
                    mock_ollama_response = MagicMock()
                    mock_ollama_response.status_code = 200
                    mock_ollama_response.json.return_value = {
                        "response": "Hello! How can I help you?"
                    }
                    
                    mock_ollama_instance = AsyncMock()
                    mock_ollama_instance.post.return_value = mock_ollama_response
                    mock_ollama.return_value.__aenter__.return_value = mock_ollama_instance
                    
                    response = await service.generate_response("Hello")
                    assert response is not None
                    assert isinstance(response, str)


@pytest.mark.asyncio
async def test_generate_response_with_cache():
    """Test generate_response với cache"""
    service = LLMService()
    
    # Mock cache service với cache hit
    with patch("services.llm_service.cache_service") as mock_cache:
        mock_cache.enabled = True
        mock_cache.get_cached_llm_response.return_value = "Cached response"
        
        response = await service.generate_response("Hello")
        # Nếu cache hit, sẽ trả về cached response
        # (cần mock đúng cách cache service hoạt động)


@pytest.mark.asyncio
async def test_check_ollama_connection():
    """Test check Ollama connection"""
    service = LLMService()
    
    with patch("services.llm_service.httpx.AsyncClient") as mock_client:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "models": [{"name": "llama3.1:latest"}]
        }
        
        mock_client_instance = AsyncMock()
        mock_client_instance.get.return_value = mock_response
        mock_client.return_value.__aenter__.return_value = mock_client_instance
        
        status = await service.check_ollama_connection()
        assert isinstance(status, dict)
        assert "connected" in status

