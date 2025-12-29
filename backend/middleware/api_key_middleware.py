"""
API Key Middleware
Middleware để log API key usage và apply rate limiting per API key
"""
import time
import logging
from fastapi import Request, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from typing import Callable, Optional

from services.api_key_service import APIKeyService

logger = logging.getLogger(__name__)


class APIKeyMiddleware(BaseHTTPMiddleware):
    """
    Middleware để:
    1. Set database session trong request state
    2. Log API key usage vào audit log
    3. Apply rate limiting per API key (nếu có)
    """

    def __init__(self, app, session_factory: Callable[[], object]):
        super().__init__(app)
        self.session_factory = session_factory

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Set database session trong request state (nếu chưa có)
        if not hasattr(request.state, "db") or request.state.db is None:
            db = self.session_factory()
            request.state.db = db
            request.state._db_created_by_middleware = True
        else:
            db = request.state.db
            request.state._db_created_by_middleware = False

        # Start time để tính response time
        start_time = time.time()

        # Process request
        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception:
            # Nếu có lỗi, vẫn log nếu có API key
            status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
            await self._log_api_key_usage(
                request, db, status_code, start_time
            )
            # Close DB nếu middleware tạo
            if getattr(request.state, "_db_created_by_middleware", False):
                try:
                    db.close()
                except Exception:
                    pass
            raise

        # Log API key usage
        await self._log_api_key_usage(
            request, db, status_code, start_time
        )

        # Close DB nếu middleware tạo (không close nếu dependency tạo)
        if getattr(request.state, "_db_created_by_middleware", False):
            try:
                db.close()
            except Exception:
                pass

        return response

    async def _log_api_key_usage(
        self,
        request: Request,
        db,
        status_code: int,
        start_time: float
    ) -> None:
        """
        Log API key usage vào audit log
        """
        try:
            # Kiểm tra xem có API key trong request state không
            api_key_obj = getattr(request.state, "api_key", None)
            if not api_key_obj or not hasattr(api_key_obj, "id"):
                return

            # Skip logging cho development mode và legacy keys
            if api_key_obj.id <= 0:
                return

            # Calculate response time
            response_time_ms = int((time.time() - start_time) * 1000)

            # Get IP address và user agent
            ip_address = request.client.host if request.client else None
            user_agent = request.headers.get("user-agent")

            # Log vào audit log
            api_key_service = APIKeyService(db)
            api_key_service.log_api_key_usage(
                api_key_id=api_key_obj.id,
                endpoint=str(request.url.path),
                method=request.method,
                ip_address=ip_address,
                user_agent=user_agent,
                status_code=status_code,
                response_time_ms=response_time_ms
            )
        except Exception as e:
            # Không fail request nếu logging có lỗi
            logger.error(f"Error logging API key usage: {e}")