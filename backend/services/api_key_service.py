"""
API Key Management Service
Quản lý API keys với multiple keys, rotation, rate limiting, và audit logging
"""
import hashlib
import secrets
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from models import APIKey, APIKeyAuditLog
import json

logger = logging.getLogger(__name__)


class APIKeyService:
    """Service để quản lý API keys"""
    
    def __init__(self, db: Session):
        self.db = db
    
    @staticmethod
    def generate_api_key() -> str:
        """
        Generate một API key mới (random secure string)
        Format: sk_live_<random_64_chars>
        """
        random_part = secrets.token_urlsafe(48)  # 48 bytes = 64 chars base64url
        return f"sk_live_{random_part}"
    
    @staticmethod
    def hash_api_key(api_key: str) -> str:
        """
        Hash API key bằng SHA-256
        Không bao giờ lưu plain text API key
        """
        return hashlib.sha256(api_key.encode()).hexdigest()
    
    def create_api_key(
        self,
        name: str,
        user_id: Optional[int] = None,
        permissions: Optional[List[str]] = None,
        rate_limit: str = "100/minute",
        expires_in_days: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Tạo API key mới
        
        Args:
            name: Tên mô tả cho API key
            user_id: User ID (optional)
            permissions: List permissions ["read", "write", "admin"]
            rate_limit: Rate limit string (e.g., "100/minute")
            expires_in_days: Số ngày trước khi expire (None = không expire)
        
        Returns:
            Dict với api_key (plain text - chỉ hiển thị 1 lần) và api_key_info
        """
        try:
            # Generate API key
            plain_api_key = self.generate_api_key()
            key_hash = self.hash_api_key(plain_api_key)
            
            # Check if hash already exists (extremely unlikely but check anyway)
            existing = self.db.query(APIKey).filter(APIKey.key_hash == key_hash).first()
            if existing:
                # Retry với key mới
                plain_api_key = self.generate_api_key()
                key_hash = self.hash_api_key(plain_api_key)
            
            # Calculate expiration date
            expires_at = None
            if expires_in_days:
                expires_at = datetime.utcnow() + timedelta(days=expires_in_days)
            
            # Create API key record
            db_api_key = APIKey(
                key_hash=key_hash,
                name=name,
                user_id=user_id,
                permissions=json.dumps(permissions) if permissions else None,
                rate_limit=rate_limit,
                expires_at=expires_at,
                is_active=True
            )
            
            self.db.add(db_api_key)
            self.db.commit()
            self.db.refresh(db_api_key)
            
            logger.info(f"Created API key: {name} (ID: {db_api_key.id})")
            
            return {
                "success": True,
                "api_key": plain_api_key,  # Chỉ trả về 1 lần duy nhất
                "api_key_info": {
                    "id": db_api_key.id,
                    "name": db_api_key.name,
                    "user_id": db_api_key.user_id,
                    "permissions": permissions or [],
                    "rate_limit": db_api_key.rate_limit,
                    "created_at": db_api_key.created_at.isoformat(),
                    "expires_at": db_api_key.expires_at.isoformat() if db_api_key.expires_at else None,
                    "is_active": db_api_key.is_active
                }
            }
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error creating API key: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def verify_api_key(self, api_key: str) -> Optional[APIKey]:
        """
        Verify API key và trả về APIKey object nếu valid
        
        Args:
            api_key: Plain text API key
        
        Returns:
            APIKey object nếu valid, None nếu không hợp lệ
        """
        try:
            key_hash = self.hash_api_key(api_key)
            
            # Find API key
            db_api_key = self.db.query(APIKey).filter(
                and_(
                    APIKey.key_hash == key_hash,
                    APIKey.is_active == True
                )
            ).first()
            
            if not db_api_key:
                return None
            
            # Check expiration
            if db_api_key.expires_at and db_api_key.expires_at < datetime.utcnow():
                logger.warning(f"API key {db_api_key.id} has expired")
                return None
            
            # Update last_used_at
            db_api_key.last_used_at = datetime.utcnow()
            self.db.commit()
            
            return db_api_key
        except Exception as e:
            logger.error(f"Error verifying API key: {e}")
            return None
    
    def rotate_api_key(self, api_key_id: int, revoke_old: bool = True) -> Dict[str, Any]:
        """
        Rotate API key: tạo key mới và có thể revoke key cũ
        
        Args:
            api_key_id: ID của API key cần rotate
            revoke_old: Có revoke key cũ không
        
        Returns:
            Dict với api_key mới và thông tin
        """
        try:
            # Get old API key
            old_key = self.db.query(APIKey).filter(APIKey.id == api_key_id).first()
            if not old_key:
                return {
                    "success": False,
                    "error": "API key not found"
                }
            
            # Create new API key với cùng settings
            permissions = json.loads(old_key.permissions) if old_key.permissions else None
            expires_in_days = None
            if old_key.expires_at:
                days_left = (old_key.expires_at - datetime.utcnow()).days
                if days_left > 0:
                    expires_in_days = days_left
            
            result = self.create_api_key(
                name=f"{old_key.name} (rotated)",
                user_id=old_key.user_id,
                permissions=permissions,
                rate_limit=old_key.rate_limit,
                expires_in_days=expires_in_days
            )
            
            if not result.get("success"):
                return result
            
            # Revoke old key nếu cần
            if revoke_old:
                old_key.is_active = False
                self.db.commit()
                logger.info(f"Rotated API key {api_key_id}: old key revoked, new key created")
            else:
                logger.info(f"Rotated API key {api_key_id}: new key created, old key still active")
            
            return result
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error rotating API key: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def revoke_api_key(self, api_key_id: int) -> Dict[str, Any]:
        """
        Revoke (deactivate) API key
        
        Args:
            api_key_id: ID của API key cần revoke
        
        Returns:
            Dict với success status
        """
        try:
            api_key = self.db.query(APIKey).filter(APIKey.id == api_key_id).first()
            if not api_key:
                return {
                    "success": False,
                    "error": "API key not found"
                }
            
            api_key.is_active = False
            self.db.commit()
            
            logger.info(f"Revoked API key {api_key_id}")
            
            return {
                "success": True,
                "message": "API key revoked successfully"
            }
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error revoking API key: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def get_api_keys(
        self,
        user_id: Optional[int] = None,
        include_inactive: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Lấy danh sách API keys
        
        Args:
            user_id: Filter theo user_id (None = tất cả)
            include_inactive: Có include inactive keys không
        
        Returns:
            List các API key info (không bao gồm plain text key)
        """
        try:
            query = self.db.query(APIKey)
            
            if user_id is not None:
                query = query.filter(APIKey.user_id == user_id)
            
            if not include_inactive:
                query = query.filter(APIKey.is_active == True)
            
            api_keys = query.order_by(APIKey.created_at.desc()).all()
            
            result = []
            for key in api_keys:
                permissions = json.loads(key.permissions) if key.permissions else []
                result.append({
                    "id": key.id,
                    "name": key.name,
                    "user_id": key.user_id,
                    "permissions": permissions,
                    "rate_limit": key.rate_limit,
                    "created_at": key.created_at.isoformat(),
                    "expires_at": key.expires_at.isoformat() if key.expires_at else None,
                    "last_used_at": key.last_used_at.isoformat() if key.last_used_at else None,
                    "is_active": key.is_active,
                    "is_expired": key.expires_at is not None and key.expires_at < datetime.utcnow() if key.expires_at else False
                })
            
            return result
        except Exception as e:
            logger.error(f"Error getting API keys: {e}")
            return []
    
    def log_api_key_usage(
        self,
        api_key_id: int,
        endpoint: str,
        method: str,
        ip_address: Optional[str],
        user_agent: Optional[str],
        status_code: int,
        response_time_ms: Optional[int] = None
    ) -> None:
        """
        Log API key usage vào audit log
        
        Args:
            api_key_id: ID của API key
            endpoint: Endpoint được gọi
            method: HTTP method
            ip_address: IP address của client
            user_agent: User agent string
            status_code: HTTP status code
            response_time_ms: Response time in milliseconds
        """
        try:
            audit_log = APIKeyAuditLog(
                api_key_id=api_key_id,
                endpoint=endpoint,
                method=method,
                ip_address=ip_address,
                user_agent=user_agent,
                status_code=status_code,
                response_time_ms=response_time_ms
            )
            
            self.db.add(audit_log)
            self.db.commit()
        except Exception as e:
            logger.error(f"Error logging API key usage: {e}")
            self.db.rollback()
    
    def get_api_key_usage_stats(
        self,
        api_key_id: int,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Lấy thống kê usage của API key
        
        Args:
            api_key_id: ID của API key
            days: Số ngày để lấy stats
        
        Returns:
            Dict với usage statistics
        """
        try:
            since_date = datetime.utcnow() - timedelta(days=days)
            
            logs = self.db.query(APIKeyAuditLog).filter(
                and_(
                    APIKeyAuditLog.api_key_id == api_key_id,
                    APIKeyAuditLog.created_at >= since_date
                )
            ).all()
            
            total_requests = len(logs)
            success_requests = len([l for l in logs if 200 <= l.status_code < 300])
            error_requests = len([l for l in logs if l.status_code >= 400])
            
            # Group by endpoint
            endpoint_counts = {}
            for log in logs:
                endpoint_counts[log.endpoint] = endpoint_counts.get(log.endpoint, 0) + 1
            
            # Average response time
            response_times = [l.response_time_ms for l in logs if l.response_time_ms]
            avg_response_time = sum(response_times) / len(response_times) if response_times else None
            
            return {
                "api_key_id": api_key_id,
                "period_days": days,
                "total_requests": total_requests,
                "success_requests": success_requests,
                "error_requests": error_requests,
                "success_rate": (success_requests / total_requests * 100) if total_requests > 0 else 0,
                "average_response_time_ms": avg_response_time,
                "endpoint_counts": endpoint_counts
            }
        except Exception as e:
            logger.error(f"Error getting API key usage stats: {e}")
            return {}
    
    def revoke_expired_keys(self) -> int:
        """
        Auto-revoke các API keys đã expired
        Chạy định kỳ như background task
        
        Returns:
            Số lượng keys đã revoke
        """
        try:
            # Sử dụng cast để đảm bảo boolean comparison hoạt động đúng
            from sqlalchemy import cast, Boolean
            
            # Query với cast để đảm bảo boolean comparison hoạt động đúng
            from sqlalchemy import cast, Boolean
            
            expired_keys = self.db.query(APIKey).filter(
                and_(
                    cast(APIKey.is_active, Boolean) == True,
                    APIKey.expires_at.isnot(None),
                    APIKey.expires_at < datetime.utcnow()
                )
            ).all()
            
            count = 0
            for key in expired_keys:
                key.is_active = False
                count += 1
            
            if count > 0:
                self.db.commit()
                logger.info(f"Auto-revoked {count} expired API keys")
            
            return count
        except Exception as e:
            logger.error(f"Error revoking expired keys: {e}")
            self.db.rollback()
            return 0
    
    def check_permission(self, api_key: APIKey, required_permission: str) -> bool:
        """
        Kiểm tra xem API key có permission cần thiết không
        
        Args:
            api_key: APIKey object
            required_permission: Permission cần kiểm tra ("read", "write", "admin")
        
        Returns:
            True nếu có permission, False nếu không
        """
        try:
            if not api_key.permissions:
                return False
            
            permissions = json.loads(api_key.permissions) if isinstance(api_key.permissions, str) else api_key.permissions
            
            # Admin có tất cả permissions
            if "admin" in permissions:
                return True
            
            return required_permission in permissions
        except Exception as e:
            logger.error(f"Error checking permission: {e}")
            return False