"""
Background Tasks Service
Các background tasks chạy định kỳ như auto-revoke expired API keys
"""
import asyncio
import logging
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from services.api_key_service import APIKeyService
import app

logger = logging.getLogger(__name__)


class BackgroundTasksService:
    """Service để quản lý các background tasks"""
    
    def __init__(self):
        self.running = False
        self.task = None
    
    async def start(self):
        """Bắt đầu background tasks"""
        if self.running:
            logger.warning("Background tasks already running")
            return
        
        self.running = True
        self.task = asyncio.create_task(self._run_periodic_tasks())
        logger.info("Background tasks started")
    
    async def stop(self):
        """Dừng background tasks"""
        self.running = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        logger.info("Background tasks stopped")
    
    async def _run_periodic_tasks(self):
        """Chạy các periodic tasks"""
        while self.running:
            try:
                # Auto-revoke expired API keys (chạy mỗi giờ)
                await self._revoke_expired_keys()
                
                # Chờ 1 giờ trước khi chạy lại
                await asyncio.sleep(3600)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in background tasks: {e}")
                # Chờ 5 phút trước khi retry nếu có lỗi
                await asyncio.sleep(300)
    
    async def _revoke_expired_keys(self):
        """Auto-revoke các API keys đã expired"""
        try:
            db = next(app.get_db())
            try:
                api_key_service = APIKeyService(db)
                count = api_key_service.revoke_expired_keys()
                if count > 0:
                    logger.info(f"Auto-revoked {count} expired API keys")
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Error revoking expired keys: {e}")


# Global instance
background_tasks_service = BackgroundTasksService()