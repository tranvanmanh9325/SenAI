"""
Response Compression Middleware
Hỗ trợ gzip compression cho responses để giảm bandwidth
"""
import logging
from starlette.middleware.gzip import GZipMiddleware
from starlette.types import ASGIApp

logger = logging.getLogger(__name__)


class CompressionMiddleware(GZipMiddleware):
    """
    GZip compression middleware cho FastAPI
    Compress responses tự động nếu client hỗ trợ gzip encoding
    """
    
    def __init__(self, app: ASGIApp, minimum_size: int = 500, compresslevel: int = 6):
        """
        Initialize compression middleware
        
        Args:
            app: ASGI application
            minimum_size: Minimum response size (bytes) để compress (default: 500)
            compresslevel: Compression level (1-9, default: 6)
        """
        super().__init__(app, minimum_size=minimum_size, compresslevel=compresslevel)
        logger.info(f"Compression middleware enabled (min_size: {minimum_size}, level: {compresslevel})")