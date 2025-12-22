"""
Rate Limiting module cho API
Sử dụng slowapi để giới hạn số lượng requests
"""
import os
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi import Request
from dotenv import load_dotenv

load_dotenv()

# Rate limiting configuration
RATE_LIMIT_ENABLED = os.getenv("RATE_LIMIT_ENABLED", "true").lower() == "true"
DEFAULT_RATE_LIMIT = os.getenv("DEFAULT_RATE_LIMIT", "100/minute")  # Format: "number/period"
STRICT_RATE_LIMIT = os.getenv("STRICT_RATE_LIMIT", "10/minute")  # Cho các endpoints quan trọng

# Initialize limiter
limiter = Limiter(
    key_func=get_remote_address,  # Sử dụng IP address để identify clients
    default_limits=[DEFAULT_RATE_LIMIT] if RATE_LIMIT_ENABLED else [],
    storage_uri="memory://",  # In-memory storage (có thể thay bằng Redis sau)
    headers_enabled=False  # Disable headers để tránh lỗi với exception handling
)


def get_rate_limit_key(request: Request) -> str:
    """
    Custom key function để rate limit dựa trên API key hoặc IP
    Nếu có API key, dùng API key; nếu không, dùng IP
    """
    # Thử lấy API key từ header
    api_key = request.headers.get("X-API-Key")
    if api_key:
        return f"api_key:{api_key}"
    
    # Fallback to IP address
    return get_remote_address(request)


# Custom limiter với key function
limiter_with_api_key = Limiter(
    key_func=get_rate_limit_key,
    default_limits=[DEFAULT_RATE_LIMIT] if RATE_LIMIT_ENABLED else [],
    storage_uri="memory://",
    headers_enabled=False  # Disable headers để tránh lỗi với exception handling
)


def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded):
    """
    Custom handler khi rate limit bị vượt quá
    """
    from fastapi import HTTPException, status
    
    raise HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail=f"Rate limit exceeded: {exc.detail}. Please try again later.",
        headers={"Retry-After": str(exc.retry_after) if hasattr(exc, 'retry_after') else "60"}
    )