"""
Celery Worker Manager
Quản lý Celery worker process chạy cùng với FastAPI app
"""
import os
import subprocess
import logging
import signal
import sys
import atexit
from typing import Optional

logger = logging.getLogger(__name__)

# Global worker process
_worker_process: Optional[subprocess.Popen] = None


def start_celery_worker():
    """Start Celery worker trong subprocess riêng"""
    global _worker_process
    
    if _worker_process is not None and _worker_process.poll() is None:
        logger.warning("Celery worker already running")
        return
    
    try:
        # Get Python executable path
        python_executable = sys.executable
        
        # Get backend directory
        backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        # Celery command
        celery_command = [
            python_executable,
            "-m",
            "celery",
            "-A",
            "services.celery_config",
            "worker",
            "--loglevel=info",
            "--pool=solo",
            "--concurrency=2",
        ]
        
        # Start worker subprocess
        # Redirect output to devnull để tránh buffer issues
        # Worker logs sẽ được handle bởi Celery's logging system
        try:
            devnull = subprocess.DEVNULL
        except AttributeError:
            # Python < 3.3 fallback
            devnull = open(os.devnull, 'wb')
        
        # start_new_session không support trên Windows, dùng False cho Windows
        start_new_session_value = os.name != 'nt'
        
        _worker_process = subprocess.Popen(
            celery_command,
            cwd=backend_dir,
            stdout=devnull,
            stderr=devnull,
            # Don't inherit file descriptors (only on non-Windows)
            start_new_session=start_new_session_value,
        )
        
        # Register cleanup function để đảm bảo worker được stop khi app exit
        atexit.register(stop_celery_worker)
        
        logger.info(f"✅ Celery worker started (PID: {_worker_process.pid})")
    except Exception as e:
        logger.error(f"❌ Failed to start Celery worker: {e}")
        _worker_process = None


def stop_celery_worker():
    """Stop Celery worker process"""
    global _worker_process
    
    if _worker_process is not None:
        try:
            if _worker_process.poll() is None:  # Process still running
                logger.info("Stopping Celery worker...")
                
                # Try graceful shutdown first (SIGTERM)
                _worker_process.terminate()
                
                try:
                    # Wait up to 5 seconds for graceful shutdown
                    _worker_process.wait(timeout=5)
                    logger.info("✅ Celery worker stopped gracefully")
                except subprocess.TimeoutExpired:
                    # Force kill if didn't stop
                    logger.warning("Celery worker did not stop gracefully, forcing kill...")
                    _worker_process.kill()
                    _worker_process.wait()
                    logger.info("✅ Celery worker killed")
        except Exception as e:
            logger.error(f"Error stopping Celery worker: {e}")
        finally:
            _worker_process = None


def is_worker_running() -> bool:
    """Check if Celery worker is running"""
    global _worker_process
    return _worker_process is not None and _worker_process.poll() is None


# Signal handlers để graceful shutdown
def setup_signal_handlers():
    """
    Setup signal handlers để graceful shutdown worker khi app shutdown
    Note: Không gọi sys.exit() trực tiếp vì sẽ gây exception trong asyncio event loop.
    Uvicorn/FastAPI sẽ tự xử lý shutdown, chúng ta chỉ cần stop worker.
    """
    def signal_handler(signum, frame):
        logger.info(f"Received signal {signum}, shutting down Celery worker...")
        stop_celery_worker()
        # Không gọi sys.exit() - để uvicorn xử lý shutdown
        # sys.exit() sẽ được gọi bởi uvicorn sau khi shutdown hoàn tất
    
    # Chỉ setup signal handlers trên Unix/Linux
    # Trên Windows, signal handlers có thể gây vấn đề với asyncio
    if hasattr(signal, 'SIGTERM'):
        try:
            signal.signal(signal.SIGTERM, signal_handler)
        except (ValueError, OSError):
            # Signal handler có thể không hoạt động trong một số môi trường
            pass
