"""
Async Helpers
Các helper functions để convert giữa sync và async operations
"""
import asyncio
import logging
from typing import Callable, Any, Coroutine
from functools import wraps

logger = logging.getLogger(__name__)


def run_async(coro: Coroutine) -> Any:
    """
    Run async coroutine từ sync context
    Handles cả trường hợp có event loop đang chạy và không có
    """
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Event loop đang chạy, dùng nest_asyncio hoặc thread pool
            try:
                import nest_asyncio
                nest_asyncio.apply()
                return loop.run_until_complete(coro)
            except ImportError:
                # Fallback: chạy trong thread pool
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, coro)
                    return future.result()
        else:
            return loop.run_until_complete(coro)
    except RuntimeError:
        # Không có event loop, tạo mới
        return asyncio.run(coro)


def async_to_sync(func: Callable) -> Callable:
    """
    Decorator để convert async function thành sync function
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        coro = func(*args, **kwargs)
        return run_async(coro)
    return wrapper


async def run_sync_in_thread(func: Callable, *args, **kwargs) -> Any:
    """
    Run sync blocking function trong thread pool từ async context
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, lambda: func(*args, **kwargs))