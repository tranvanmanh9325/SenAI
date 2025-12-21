"""
Middleware để track HTTP requests và response times
"""
import time
import logging
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response as StarletteResponse

logger = logging.getLogger(__name__)

# Import metrics service
try:
    from services.metrics_service import metrics_service
    METRICS_AVAILABLE = True
except ImportError:
    METRICS_AVAILABLE = False
    metrics_service = None
    logger.warning("Metrics service not available")

class MetricsMiddleware(BaseHTTPMiddleware):
    """Middleware để track HTTP metrics"""
    
    async def dispatch(self, request: Request, call_next):
        """Process request and track metrics"""
        start_time = time.time()
        
        # Get method and path
        method = request.method
        path = request.url.path
        
        # Skip metrics endpoint itself
        if path == "/metrics":
            return await call_next(request)
        
        try:
            # Process request
            response = await call_next(request)
            
            # Calculate duration
            duration = time.time() - start_time
            
            # Record metrics
            if METRICS_AVAILABLE and metrics_service and metrics_service.enabled:
                metrics_service.record_http_request(
                    method=method,
                    endpoint=path,
                    status_code=response.status_code,
                    duration=duration
                )
            
            # Add response headers
            response.headers["X-Process-Time"] = str(round(duration, 4))
            
            return response
            
        except Exception as e:
            # Calculate duration even on error
            duration = time.time() - start_time
            
            # Record error metrics
            if METRICS_AVAILABLE and metrics_service and metrics_service.enabled:
                metrics_service.record_http_request(
                    method=method,
                    endpoint=path,
                    status_code=500,
                    duration=duration
                )
                metrics_service.record_error(
                    error_type=type(e).__name__,
                    service="http"
                )
            
            # Re-raise exception
            raise

