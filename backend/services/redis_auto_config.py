"""
Redis Auto-Configuration
Tự động detect và cấu hình Redis connection
"""
import os
import logging
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


def detect_redis_host() -> Tuple[str, bool]:
    """
    Tự động detect Redis host bằng cách thử kết nối
    
    Returns:
        Tuple[host, success]: (redis_host, connection_successful)
    """
    import redis
    
    # Danh sách hosts để thử (theo thứ tự ưu tiên)
    hosts_to_try = [
        "localhost",
        "127.0.0.1",
        # Có thể thêm các IP khác nếu cần
    ]
    
    # Lấy port từ env hoặc dùng default
    port = int(os.getenv("REDIS_PORT", "6379"))
    timeout = int(os.getenv("REDIS_CONNECT_TIMEOUT", "5"))
    
    for host in hosts_to_try:
        try:
            r = redis.Redis(
                host=host,
                port=port,
                db=0,
                socket_connect_timeout=timeout,
                decode_responses=True
            )
            r.ping()
            logger.info(f"Auto-detected Redis at {host}:{port}")
            return host, True
        except (redis.ConnectionError, redis.TimeoutError, Exception):
            continue
    
    # Nếu không connect được, trả về localhost (default)
    return "localhost", False


def auto_configure_redis() -> str:
    """
    Tự động cấu hình Redis host và update environment variable nếu cần
    
    Returns:
        str: Redis host được sử dụng
    """
    # Nếu đã có REDIS_HOST trong env và không phải auto-detect, dùng giá trị đó
    redis_host_env = os.getenv("REDIS_HOST")
    auto_detect = os.getenv("REDIS_AUTO_DETECT", "true").lower() == "true"
    
    if redis_host_env and not auto_detect:
        # Nếu đã config và không muốn auto-detect, dùng giá trị hiện tại
        return redis_host_env
    
    # Nếu REDIS_HOST không được set hoặc muốn auto-detect, thử detect
    if not redis_host_env or auto_detect:
        try:
            detected_host, success = detect_redis_host()
        except ImportError:
            # Redis module chưa được cài, dùng default
            logger.debug("Redis module not available for auto-detection, using default")
            return redis_host_env or "localhost"
        
        if success:
            # Update environment variable cho session này
            os.environ["REDIS_HOST"] = detected_host
            if detected_host != redis_host_env:
                logger.info(f"Auto-configured REDIS_HOST: {redis_host_env or 'not set'} -> {detected_host}")
            return detected_host
        else:
            # Nếu không detect được, dùng giá trị hiện tại hoặc localhost
            if redis_host_env:
                logger.warning(f"Cannot connect to Redis at {redis_host_env}, but keeping configuration")
                return redis_host_env
            else:
                logger.warning("Cannot auto-detect Redis, using default: localhost")
                os.environ["REDIS_HOST"] = "localhost"
                return "localhost"
    else:
        # Dùng giá trị đã config
        return redis_host_env
