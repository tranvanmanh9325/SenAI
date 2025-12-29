"""
Security Headers Middleware
Middleware để thêm security headers và enforce TLS/SSL
"""
import os
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
from fastapi import Request, status
from fastapi.responses import Response
from starlette.responses import RedirectResponse


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Middleware để thêm security headers và enforce HTTPS
    """
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
        # Cấu hình từ environment variables
        self.enforce_https = os.getenv("ENFORCE_HTTPS", "false").lower() == "true"
        self.hsts_max_age = int(os.getenv("HSTS_MAX_AGE", "31536000"))  # 1 year default
    
    async def dispatch(self, request: Request, call_next):
        """Add security headers và enforce HTTPS nếu cần"""
        
        # Enforce HTTPS nếu được cấu hình
        if self.enforce_https:
            # Kiểm tra nếu request không phải HTTPS
            if request.url.scheme != "https":
                # Redirect to HTTPS
                https_url = request.url.replace(scheme="https")
                return RedirectResponse(url=str(https_url), status_code=status.HTTP_301_MOVED_PERMANENTLY)
        
        # Process request
        response = await call_next(request)
        
        # Add security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        
        # HSTS header (chỉ khi HTTPS)
        if request.url.scheme == "https" or self.enforce_https:
            response.headers["Strict-Transport-Security"] = f"max-age={self.hsts_max_age}; includeSubDomains"
        
        # Content Security Policy (có thể customize)
        csp = os.getenv(
            "CONTENT_SECURITY_POLICY",
            "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline';"
        )
        response.headers["Content-Security-Policy"] = csp
        
        # Permissions Policy (trước đây là Feature-Policy)
        response.headers["Permissions-Policy"] = (
            "geolocation=(), microphone=(), camera=(), "
            "payment=(), usb=(), magnetometer=(), gyroscope=()"
        )
        
        return response

