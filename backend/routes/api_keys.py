"""
API Key Management Routes
Endpoints để quản lý API keys: GET/POST/DELETE /api/keys
"""
from fastapi import APIRouter, HTTPException, Depends, Request
from sqlalchemy.orm import Session
from typing import Optional, List
from pydantic import BaseModel, Field
import logging

from middleware.auth import verify_api_key, require_permission
from middleware.rate_limit import limiter_with_api_key, STRICT_RATE_LIMIT
from services.api_key_service import APIKeyService
from models import APIKey
import app

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/keys", tags=["API Keys"])

# Pydantic models
class APIKeyCreate(BaseModel):
    name: str = Field(..., description="Tên mô tả cho API key")
    user_id: Optional[int] = Field(None, description="User ID (optional)")
    permissions: Optional[List[str]] = Field(
        default=["read", "write"],
        description="List permissions: ['read', 'write', 'admin']"
    )
    rate_limit: str = Field(
        default="100/minute",
        description="Rate limit string (e.g., '100/minute', '1000/hour')"
    )
    expires_in_days: Optional[int] = Field(
        None,
        description="Số ngày trước khi expire (None = không expire)"
    )


class APIKeyResponse(BaseModel):
    id: int
    name: str
    user_id: Optional[int]
    permissions: List[str]
    rate_limit: str
    created_at: str
    expires_at: Optional[str]
    last_used_at: Optional[str]
    is_active: bool
    is_expired: bool


class APIKeyCreateResponse(BaseModel):
    success: bool
    api_key: Optional[str] = None  # Plain text key (chỉ hiển thị 1 lần)
    api_key_info: Optional[APIKeyResponse] = None
    error: Optional[str] = None


class APIKeyRotateRequest(BaseModel):
    revoke_old: bool = Field(
        default=True,
        description="Có revoke key cũ không"
    )


class APIKeyUsageStats(BaseModel):
    api_key_id: int
    period_days: int
    total_requests: int
    success_requests: int
    error_requests: int
    success_rate: float
    average_response_time_ms: Optional[float]
    endpoint_counts: dict


# Get database dependency
def get_db(request: Request) -> Session:
    """Get database session từ request state"""
    db = getattr(request.state, "db", None)
    if not db:
        db = next(app.get_db())
        request.state.db = db
    return db


@router.get("", response_model=List[APIKeyResponse])
@limiter_with_api_key.limit(STRICT_RATE_LIMIT)
async def list_api_keys(
    request: Request,
    user_id: Optional[int] = None,
    include_inactive: bool = False,
    db: Session = Depends(get_db),
    api_key: APIKey = Depends(require_permission("admin"))
):
    """
    Lấy danh sách API keys
    
    - **user_id**: Filter theo user_id (optional)
    - **include_inactive**: Có include inactive keys không
    - Yêu cầu permission: admin
    """
    try:
        api_key_service = APIKeyService(db)
        api_keys = api_key_service.get_api_keys(
            user_id=user_id,
            include_inactive=include_inactive
        )
        
        return api_keys
    except Exception as e:
        logger.error(f"Error listing API keys: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error listing API keys: {str(e)}"
        )


@router.post("", response_model=APIKeyCreateResponse)
@limiter_with_api_key.limit(STRICT_RATE_LIMIT)
async def create_api_key(
    request: Request,
    api_key_data: APIKeyCreate,
    db: Session = Depends(get_db),
    current_api_key: APIKey = Depends(require_permission("admin"))
):
    """
    Tạo API key mới
    
    - **name**: Tên mô tả cho API key
    - **user_id**: User ID (optional)
    - **permissions**: List permissions ["read", "write", "admin"]
    - **rate_limit**: Rate limit string (e.g., "100/minute")
    - **expires_in_days**: Số ngày trước khi expire (None = không expire)
    - Yêu cầu permission: admin
    
    **Lưu ý**: API key plain text chỉ được trả về 1 lần duy nhất khi tạo.
    Hãy lưu lại ngay vì không thể xem lại sau này.
    """
    try:
        api_key_service = APIKeyService(db)
        result = api_key_service.create_api_key(
            name=api_key_data.name,
            user_id=api_key_data.user_id,
            permissions=api_key_data.permissions,
            rate_limit=api_key_data.rate_limit,
            expires_in_days=api_key_data.expires_in_days
        )
        
        if not result.get("success"):
            raise HTTPException(
                status_code=400,
                detail=result.get("error", "Failed to create API key")
            )
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating API key: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error creating API key: {str(e)}"
        )


@router.delete("/{api_key_id}")
@limiter_with_api_key.limit(STRICT_RATE_LIMIT)
async def revoke_api_key(
    request: Request,
    api_key_id: int,
    db: Session = Depends(get_db),
    current_api_key: APIKey = Depends(require_permission("admin"))
):
    """
    Revoke (deactivate) API key
    
    - **api_key_id**: ID của API key cần revoke
    - Yêu cầu permission: admin
    """
    try:
        api_key_service = APIKeyService(db)
        result = api_key_service.revoke_api_key(api_key_id)
        
        if not result.get("success"):
            raise HTTPException(
                status_code=400,
                detail=result.get("error", "Failed to revoke API key")
            )
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error revoking API key: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error revoking API key: {str(e)}"
        )


@router.post("/{api_key_id}/rotate", response_model=APIKeyCreateResponse)
@limiter_with_api_key.limit(STRICT_RATE_LIMIT)
async def rotate_api_key(
    request: Request,
    api_key_id: int,
    rotate_data: APIKeyRotateRequest,
    db: Session = Depends(get_db),
    current_api_key: APIKey = Depends(require_permission("admin"))
):
    """
    Rotate API key: tạo key mới và có thể revoke key cũ
    
    - **api_key_id**: ID của API key cần rotate
    - **revoke_old**: Có revoke key cũ không (default: True)
    - Yêu cầu permission: admin
    
    **Lưu ý**: API key mới chỉ được trả về 1 lần duy nhất khi rotate.
    Hãy lưu lại ngay vì không thể xem lại sau này.
    """
    try:
        api_key_service = APIKeyService(db)
        result = api_key_service.rotate_api_key(
            api_key_id=api_key_id,
            revoke_old=rotate_data.revoke_old
        )
        
        if not result.get("success"):
            raise HTTPException(
                status_code=400,
                detail=result.get("error", "Failed to rotate API key")
            )
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error rotating API key: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error rotating API key: {str(e)}"
        )


@router.get("/{api_key_id}/stats", response_model=APIKeyUsageStats)
@limiter_with_api_key.limit(STRICT_RATE_LIMIT)
async def get_api_key_stats(
    request: Request,
    api_key_id: int,
    days: int = 30,
    db: Session = Depends(get_db),
    current_api_key: APIKey = Depends(require_permission("admin"))
):
    """
    Lấy thống kê usage của API key
    
    - **api_key_id**: ID của API key
    - **days**: Số ngày để lấy stats (default: 30)
    - Yêu cầu permission: admin
    """
    try:
        api_key_service = APIKeyService(db)
        stats = api_key_service.get_api_key_usage_stats(
            api_key_id=api_key_id,
            days=days
        )
        
        if not stats:
            raise HTTPException(
                status_code=404,
                detail="API key not found or no usage data"
            )
        
        return stats
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting API key stats: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error getting API key stats: {str(e)}"
        )


@router.get("/{api_key_id}", response_model=APIKeyResponse)
@limiter_with_api_key.limit(STRICT_RATE_LIMIT)
async def get_api_key(
    request: Request,
    api_key_id: int,
    db: Session = Depends(get_db),
    current_api_key: APIKey = Depends(require_permission("admin"))
):
    """
    Lấy thông tin của một API key
    
    - **api_key_id**: ID của API key
    - Yêu cầu permission: admin
    """
    try:
        api_key_service = APIKeyService(db)
        api_keys = api_key_service.get_api_keys(include_inactive=True)
        
        api_key = next((k for k in api_keys if k["id"] == api_key_id), None)
        if not api_key:
            raise HTTPException(
                status_code=404,
                detail="API key not found"
            )
        
        return api_key
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting API key: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error getting API key: {str(e)}"
        )