"""
Pydantic models for request/response validation.
This module contains all Pydantic models used for API request and response validation.
"""
from pydantic import BaseModel, ConfigDict, field_validator
from datetime import datetime
from typing import Optional, Dict

# Input validation & security helpers
from middleware.security import (
    validate_and_sanitize_text,
    MAX_MESSAGE_LENGTH,
    MAX_TASK_NAME_LENGTH,
    MAX_COMMENT_LENGTH,
    MAX_SESSION_ID_LENGTH,
)


class TaskCreate(BaseModel):
    task_name: str
    description: Optional[str] = None

    model_config = ConfigDict(str_strip_whitespace=True)

    @field_validator("task_name")
    @classmethod
    def validate_task_name(cls, v: str) -> str:
        return validate_and_sanitize_text(
            v,
            max_length=MAX_TASK_NAME_LENGTH,
            field_name="task_name",
            allow_empty=False,
        )

    @field_validator("description")
    @classmethod
    def validate_description(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        return validate_and_sanitize_text(
            v,
            max_length=MAX_COMMENT_LENGTH,
            field_name="description",
            allow_empty=True,
        )


class TaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    task_name: str
    description: Optional[str]
    status: str
    result: Optional[str]
    created_at: datetime
    updated_at: datetime


class ConversationCreate(BaseModel):
    user_message: str
    session_id: Optional[str] = None

    model_config = ConfigDict(str_strip_whitespace=True)

    @field_validator("user_message")
    @classmethod
    def validate_user_message(cls, v: str) -> str:
        return validate_and_sanitize_text(
            v,
            max_length=MAX_MESSAGE_LENGTH,
            field_name="user_message",
            allow_empty=False,
        )

    @field_validator("session_id")
    @classmethod
    def validate_session_id(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        return validate_and_sanitize_text(
            v,
            max_length=MAX_SESSION_ID_LENGTH,
            field_name="session_id",
            allow_empty=False,
        )


class ConversationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    user_message: str
    ai_response: Optional[str]
    session_id: Optional[str]
    created_at: datetime


class FeedbackCreate(BaseModel):
    conversation_id: int
    rating: Optional[int] = None  # 1-5 stars
    feedback_type: str = "rating"  # rating, thumbs_up, thumbs_down, detailed
    comment: Optional[str] = None
    user_correction: Optional[str] = None  # Câu trả lời đúng nếu user muốn sửa
    is_helpful: Optional[str] = None  # yes, no, partially

    model_config = ConfigDict(str_strip_whitespace=True)

    @field_validator("rating")
    @classmethod
    def validate_rating(cls, v: Optional[int]) -> Optional[int]:
        if v is None:
            return v
        if v < 1 or v > 5:
            raise ValueError("rating must be between 1 and 5")
        return v

    @field_validator("feedback_type")
    @classmethod
    def validate_feedback_type(cls, v: str) -> str:
        allowed = {"rating", "thumbs_up", "thumbs_down", "detailed"}
        if v not in allowed:
            raise ValueError(f"feedback_type must be one of {sorted(allowed)}")
        return v

    @field_validator("is_helpful")
    @classmethod
    def validate_is_helpful(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        allowed = {"yes", "no", "partially"}
        if v not in allowed:
            raise ValueError(f"is_helpful must be one of {sorted(allowed)}")
        return v

    @field_validator("comment")
    @classmethod
    def validate_comment(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        return validate_and_sanitize_text(
            v,
            max_length=MAX_COMMENT_LENGTH,
            field_name="comment",
            allow_empty=True,
        )

    @field_validator("user_correction")
    @classmethod
    def validate_user_correction(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        return validate_and_sanitize_text(
            v,
            max_length=MAX_MESSAGE_LENGTH,
            field_name="user_correction",
            allow_empty=False,
        )


class FeedbackResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    conversation_id: int
    rating: Optional[int]
    feedback_type: str
    comment: Optional[str]
    user_correction: Optional[str]
    is_helpful: Optional[str]
    created_at: datetime
    updated_at: datetime


class FeedbackStats(BaseModel):
    total_feedback: int
    average_rating: Optional[float]
    positive_count: int
    negative_count: int
    neutral_count: int
    helpful_count: int
    not_helpful_count: int
    feedback_by_type: Dict[str, int]