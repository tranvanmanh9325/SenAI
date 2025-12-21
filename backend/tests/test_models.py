"""
Tests cho Database Models
"""
import pytest
from datetime import datetime
from models import (
    AgentTask,
    AgentConversation,
    ConversationFeedback,
    ConversationEmbedding
)


def test_agent_task_model():
    """Test AgentTask model"""
    task = AgentTask(
        task_name="Test Task",
        description="Test Description",
        status="pending"
    )
    assert task.task_name == "Test Task"
    assert task.description == "Test Description"
    assert task.status == "pending"
    assert isinstance(task.created_at, datetime) or task.created_at is None


def test_agent_conversation_model():
    """Test AgentConversation model"""
    conversation = AgentConversation(
        user_message="Hello",
        ai_response="Hi there!",
        session_id="test-session"
    )
    assert conversation.user_message == "Hello"
    assert conversation.ai_response == "Hi there!"
    assert conversation.session_id == "test-session"
    assert isinstance(conversation.created_at, datetime) or conversation.created_at is None


def test_conversation_feedback_model():
    """Test ConversationFeedback model"""
    feedback = ConversationFeedback(
        conversation_id=1,
        rating=5,
        feedback_type="rating",
        comment="Great!",
        is_helpful="yes"
    )
    assert feedback.conversation_id == 1
    assert feedback.rating == 5
    assert feedback.feedback_type == "rating"
    assert feedback.comment == "Great!"
    assert feedback.is_helpful == "yes"
    assert isinstance(feedback.created_at, datetime) or feedback.created_at is None


def test_conversation_embedding_model():
    """Test ConversationEmbedding model"""
    embedding = ConversationEmbedding(
        conversation_id=1,
        user_message_embedding="[0.1,0.2,0.3]",
        ai_response_embedding="[0.4,0.5,0.6]",
        combined_embedding="[0.7,0.8,0.9]",
        embedding_model="sentence-transformers",
        embedding_dimension=384
    )
    assert embedding.conversation_id == 1
    assert embedding.user_message_embedding == "[0.1,0.2,0.3]"
    assert embedding.embedding_model == "sentence-transformers"
    assert embedding.embedding_dimension == 384
    assert isinstance(embedding.created_at, datetime) or embedding.created_at is None

