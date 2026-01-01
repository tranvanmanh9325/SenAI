"""
Logging Middleware
Middleware để mask sensitive data trong logs
"""
import logging
import re
from typing import Optional
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
from fastapi import Request


class SensitiveDataFilter(logging.Filter):
    """
    Logging filter để mask sensitive data trong log messages
    """
    
    # Patterns để detect sensitive data
    SENSITIVE_PATTERNS = [
        # API keys (sk_live_..., sk_test_..., etc.)
        (r'sk_(live|test)_[A-Za-z0-9_-]{20,}', 'sk_***'),
        # Passwords trong URLs (postgresql://user:password@host)
        (r'(postgresql|mysql|mongodb)://[^:]+:([^@]+)@', r'\1://***:***@'),
        # Passwords trong connection strings
        (r'password[=:]\s*([^\s&"\']+)', 'password=***'),
        # API keys trong headers
        (r'(api[_-]?key|authorization|bearer)\s*[:=]\s*([^\s"\']+)', r'\1=***'),
        # Email addresses (optional - có thể bỏ nếu cần)
        # (r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '***@***.***'),
        # Credit card numbers (basic pattern)
        (r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b', '****-****-****-****'),
        # SSN (US)
        (r'\b\d{3}-\d{2}-\d{4}\b', '***-**-****'),
    ]
    
    def filter(self, record: logging.LogRecord) -> bool:
        """
        Filter log record và mask sensitive data
        
        Args:
            record: Log record
        
        Returns:
            True để cho phép log, False để reject
        """
        if hasattr(record, 'msg') and record.msg:
            # Mask trong message
            record.msg = self._mask_sensitive_data(str(record.msg))
        
        if hasattr(record, 'args') and record.args:
            # Mask trong args
            masked_args = []
            for arg in record.args:
                if isinstance(arg, str):
                    masked_args.append(self._mask_sensitive_data(arg))
                else:
                    masked_args.append(arg)
            record.args = tuple(masked_args)
        
        return True
    
    @staticmethod
    def _mask_sensitive_data(text: str) -> str:
        """
        Mask sensitive data trong text
        
        Args:
            text: Text cần mask
        
        Returns:
            Masked text
        """
        if not text:
            return text
        
        masked = text
        for pattern, replacement in SensitiveDataFilter.SENSITIVE_PATTERNS:
            if isinstance(replacement, str):
                masked = re.sub(pattern, replacement, masked, flags=re.IGNORECASE)
            else:
                masked = re.sub(pattern, replacement, masked, flags=re.IGNORECASE)
        
        return masked


class SecureLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware để đảm bảo sensitive data không bị log
    """
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
        # Thêm filter vào tất cả loggers
        self._setup_logging_filters()
    
    def _setup_logging_filters(self):
        """Setup sensitive data filter cho tất cả loggers"""
        filter_instance = SensitiveDataFilter()
        
        # Apply filter cho root logger và tất cả child loggers
        root_logger = logging.getLogger()
        root_logger.addFilter(filter_instance)
        
        # Apply cho các loggers cụ thể
        for logger_name in ['uvicorn', 'fastapi', 'sqlalchemy', '__main__']:
            logger = logging.getLogger(logger_name)
            logger.addFilter(filter_instance)
    
    async def dispatch(self, request: Request, call_next):
        """Process request và đảm bảo không log sensitive data"""
        # Mask sensitive headers trước khi log
        masked_headers = dict(request.headers)
        if 'authorization' in masked_headers:
            masked_headers['authorization'] = 'Bearer ***'
        if 'x-api-key' in masked_headers:
            masked_headers['x-api-key'] = '***'
        
        # Store masked headers trong request state để sử dụng sau
        request.state.masked_headers = masked_headers
        
        response = await call_next(request)
        return response