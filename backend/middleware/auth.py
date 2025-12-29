"""
Authentication module cho API
Hỗ trợ API key authentication với multiple keys từ database
"""
import os
import logging
from fastapi import Security, HTTPException, status, Request, Depends
from fastapi.security import APIKeyHeader
from typing import Optional
from sqlalchemy.orm import Session
from dotenv import load_dotenv

from services.api_key_service import APIKeyService
from models import APIKey

logger = logging.getLogger(__name__)

load_dotenv()

# API Key configuration
API_KEY_HEADER_NAME = "X-API-Key"
API_KEY_ENV = os.getenv("API_KEY", "")  # Legacy support
REQUIRE_API_KEY = os.getenv("REQUIRE_API_KEY", "false").lower() == "true"
USE_DATABASE_API_KEYS = os.getenv("USE_DATABASE_API_KEYS", "true").lower() == "true"

# API Key Header
api_key_header = APIKeyHeader(name=API_KEY_HEADER_NAME, auto_error=False)


def get_db_from_request(request: Request) -> Session:
    """
    Get database session từ request state
    Được set bởi middleware hoặc dependency
    """
    if not hasattr(request.state, "db") or request.state.db is None:
        # Fallback: import từ app
        import app
        db = next(app.get_db())
        request.state.db = db
        return db
    return request.state.db


async def verify_api_key(
    request: Request,
    api_key: Optional[str] = Security(api_key_header)
) -> APIKey:
    """
    Verify API key từ request header
    Hỗ trợ cả legacy env API key và database API keys
    
    Args:
        request: FastAPI Request object (injected)
        api_key: API key từ header X-API-Key
        
    Returns:
        APIKey object nếu valid
        
    Raises:
        HTTPException nếu API key không hợp lệ
    """
    # Nếu không yêu cầu API key (development mode)
    if not REQUIRE_API_KEY:
        # Return a mock APIKey object for development
        class MockAPIKey:
            id = 0
            name = "development_mode"
            user_id = None
            permissions = None
            rate_limit = "1000/minute"
            is_active = True
        
        mock_key = MockAPIKey()
        request.state.api_key = mock_key
        return mock_key
    
    # Kiểm tra API key
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key missing. Please provide X-API-Key header.",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    
    # Nếu sử dụng database API keys (recommended)
    if USE_DATABASE_API_KEYS:
        try:
            # Get database session từ request state hoặc create new
            db = getattr(request.state, "db", None)
            if not db:
                import app
                db = next(app.get_db())
                request.state.db = db
            
            # Verify với database
            api_key_service = APIKeyService(db)
            db_api_key = api_key_service.verify_api_key(api_key)
            
            if db_api_key:
                # Store API key object trong request state để dùng sau
                request.state.api_key = db_api_key
                return db_api_key
            
            # Nếu không tìm thấy trong database, thử legacy env key
            if API_KEY_ENV and api_key == API_KEY_ENV:
                logger.warning("Using legacy API key from environment. Consider migrating to database API keys.")
                class LegacyAPIKey:
                    id = -1
                    name = "legacy_env_key"
                    user_id = None
                    permissions = None
                    rate_limit = "100/minute"
                    is_active = True
                
                legacy_key = LegacyAPIKey()
                request.state.api_key = legacy_key
                return legacy_key
            
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid API key.",
                headers={"WWW-Authenticate": "ApiKey"},
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error verifying API key: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error verifying API key.",
            )
    else:
        # Legacy mode: chỉ dùng env API key
        if not API_KEY_ENV:
            logger.warning("API_KEY not set in environment. Allowing all requests in development mode.")
            class MockAPIKey:
                id = 0
                name = "development_mode"
                user_id = None
                permissions = None
                rate_limit = "1000/minute"
                is_active = True
            mock_key = MockAPIKey()
            request.state.api_key = mock_key
            return mock_key
        
        if api_key != API_KEY_ENV:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid API key.",
                headers={"WWW-Authenticate": "ApiKey"},
            )
        
        class LegacyAPIKey:
            id = -1
            name = "legacy_env_key"
            user_id = None
            permissions = None
            rate_limit = "100/minute"
            is_active = True
        
        legacy_key = LegacyAPIKey()
        request.state.api_key = legacy_key
        return legacy_key


async def optional_api_key(
    request: Request,
    api_key: Optional[str] = Security(api_key_header)
) -> Optional[APIKey]:
    """
    Optional API key verification (không bắt buộc)
    Dùng cho các endpoints có thể public hoặc protected
    """
    if not REQUIRE_API_KEY:
        return None
    
    if not api_key:
        return None
    
    try:
        return await verify_api_key(request, api_key)
    except HTTPException:
        return None


def require_permission(permission: str):
    """
    Dependency để kiểm tra permission của API key
    
    Usage:
        @router.get("/admin")
        async def admin_endpoint(
            request: Request,
            api_key: APIKey = Depends(require_permission("admin"))
        ):
            ...
    """
    async def permission_checker(
        request: Request,
        api_key: APIKey = Depends(verify_api_key)
    ) -> APIKey:
        from services.api_key_service import APIKeyService
        import app
        
        # Get database session
        db = getattr(request.state, "db", None)
        if not db:
            db = next(app.get_db())
            request.state.db = db
        
        api_key_service = APIKeyService(db)
        
        if not api_key_service.check_permission(api_key, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required: {permission}",
            )
        
        return api_key
    
    return permission_checker