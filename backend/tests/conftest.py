"""
Pytest configuration và fixtures
"""
import pytest
import os
import sys
from pathlib import Path

# Add backend directory to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

# Set test environment variables
os.environ["TESTING"] = "true"
os.environ["LLM_PROVIDER"] = "ollama"
os.environ["OLLAMA_BASE_URL"] = "http://localhost:11434"
os.environ["REQUIRE_API_KEY"] = "false"
os.environ["RATE_LIMIT_ENABLED"] = "false"
os.environ["REDIS_ENABLED"] = "false"
os.environ["USE_PGVECTOR"] = "false"

@pytest.fixture
def mock_db_session():
    """Mock database session"""
    from unittest.mock import MagicMock
    return MagicMock()

@pytest.fixture
def sample_conversation_data():
    """Sample conversation data for testing"""
    return {
        "user_message": "Hello, how are you?",
        "session_id": "test-session-123",
        "ai_response": "I'm doing well, thank you!"
    }

@pytest.fixture
def sample_feedback_data():
    """Sample feedback data for testing"""
    return {
        "conversation_id": 1,
        "rating": 5,
        "feedback_type": "rating",
        "comment": "Great response!",
        "is_helpful": "yes"
    }

