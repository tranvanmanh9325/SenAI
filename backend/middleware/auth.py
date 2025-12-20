"""
Authentication module cho API
Hỗ trợ API key authentication
"""
import os
import logging
from fastapi import Security, HTTPException, status
from fastapi.security import APIKeyHeader
from typing import Optional
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

load_dotenv()

# API Key configuration
API_KEY_HEADER_NAME = "X-API-Key"
API_KEY_ENV = os.getenv("API_KEY", "")
REQUIRE_API_KEY = os.getenv("REQUIRE_API_KEY", "false").lower() == "true"

# API Key Header
api_key_header = APIKeyHeader(name=API_KEY_HEADER_NAME, auto_error=False)


async def verify_api_key(api_key: Optional[str] = Security(api_key_header)) -> str:
    """
    Verify API key từ request header
    
    Args:
        api_key: API key từ header X-API-Key
        
    Returns:
        API key nếu valid
        
    Raises:
        HTTPException nếu API key không hợp lệ
    """
    # Nếu không yêu cầu API key (development mode)
    if not REQUIRE_API_KEY:
        return "development_mode"
    
    # Nếu không có API key được cấu hình
    if not API_KEY_ENV:
        # Trong development, cho phép không có API key
        logger.warning("API_KEY not set in environment. Allowing all requests in development mode.")
        return "development_mode"
    
    # Kiểm tra API key
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key missing. Please provide X-API-Key header.",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    
    if api_key != API_KEY_ENV:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API key.",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    
    return api_key


async def optional_api_key(api_key: Optional[str] = Security(api_key_header)) -> Optional[str]:
    """
    Optional API key verification (không bắt buộc)
    Dùng cho các endpoints có thể public hoặc protected
    """
    if not REQUIRE_API_KEY or not API_KEY_ENV:
        return None
    
    if api_key and api_key == API_KEY_ENV:
        return api_key
    
    return None