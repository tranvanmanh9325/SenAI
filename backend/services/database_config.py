"""
Database Configuration Module
Cung cấp cấu hình tối ưu cho database connection pooling, read replicas, và query optimization
"""
import os
from typing import Optional, Dict, Any
from sqlalchemy import create_engine, Engine
from sqlalchemy.pool import QueuePool
import logging

logger = logging.getLogger(__name__)


class DatabaseConfig:
    """Quản lý cấu hình database connection pooling và read replicas"""
    
    def __init__(self):
        # Database configuration từ environment variables
        self.db_host = os.getenv("DB_HOST", "192.168.0.106")
        self.db_port = os.getenv("DB_PORT", "5432")
        self.db_name = os.getenv("DB_NAME", "ai_system")
        self.db_user = os.getenv("DB_USER", "postgres")
        self.db_password = os.getenv("DB_PASSWORD", "")
        
        # SSL configuration
        self.db_ssl_mode = os.getenv("DB_SSL_MODE", "prefer")
        self.db_ssl_root_cert = os.getenv("DB_SSL_ROOT_CERT", None)
        self.db_ssl_cert = os.getenv("DB_SSL_CERT", None)
        self.db_ssl_key = os.getenv("DB_SSL_KEY", None)
        
        # Connection pooling configuration
        # Pool size: số lượng connections giữ trong pool
        # Nên set = (2 * số CPU cores) + số disk spindles
        self.pool_size = int(os.getenv("DB_POOL_SIZE", "10"))
        
        # Max overflow: số connections có thể vượt quá pool_size
        # Tổng max connections = pool_size + max_overflow
        self.max_overflow = int(os.getenv("DB_MAX_OVERFLOW", "20"))
        
        # Pool recycle: thời gian (seconds) trước khi recycle connection
        # Tránh stale connections, PostgreSQL thường timeout sau 1 giờ
        self.pool_recycle = int(os.getenv("DB_POOL_RECYCLE", "3600"))
        
        # Pool timeout: thời gian chờ khi lấy connection từ pool
        self.pool_timeout = int(os.getenv("DB_POOL_TIMEOUT", "30"))
        
        # Pool pre ping: kiểm tra connection trước khi sử dụng
        self.pool_pre_ping = os.getenv("DB_POOL_PRE_PING", "true").lower() == "true"
        
        # Read replica configuration
        self.read_replica_host = os.getenv("DB_READ_REPLICA_HOST", None)
        self.read_replica_port = os.getenv("DB_READ_REPLICA_PORT", self.db_port)
        self.read_replica_name = os.getenv("DB_READ_REPLICA_NAME", self.db_name)
        self.read_replica_user = os.getenv("DB_READ_REPLICA_USER", self.db_user)
        self.read_replica_password = os.getenv("DB_READ_REPLICA_PASSWORD", self.db_password)
        
        # Connection timeout
        self.connect_timeout = int(os.getenv("DB_CONNECT_TIMEOUT", "10"))
        
        # Statement timeout (milliseconds) - kill queries chạy quá lâu
        self.statement_timeout = os.getenv("DB_STATEMENT_TIMEOUT", None)  # None = no timeout
        
        # Application name cho PostgreSQL logging
        self.application_name = os.getenv("DB_APPLICATION_NAME", "ai_agent_backend")
    
    def _build_connect_args(self) -> Dict[str, Any]:
        """Xây dựng connection arguments"""
        connect_args = {
            "connect_timeout": self.connect_timeout,
            "sslmode": self.db_ssl_mode,
            "application_name": self.application_name
        }
        
        # Add SSL certificates nếu có
        if self.db_ssl_root_cert:
            connect_args["sslrootcert"] = self.db_ssl_root_cert
        if self.db_ssl_cert:
            connect_args["sslcert"] = self.db_ssl_cert
        if self.db_ssl_key:
            connect_args["sslkey"] = self.db_ssl_key
        
        # Statement timeout
        if self.statement_timeout:
            connect_args["options"] = f"-c statement_timeout={self.statement_timeout}"
        
        return connect_args
    
    def _build_database_url(self, host: Optional[str] = None, port: Optional[str] = None,
                           name: Optional[str] = None, user: Optional[str] = None,
                           password: Optional[str] = None) -> str:
        """Xây dựng database URL"""
        host = host or self.db_host
        port = port or self.db_port
        name = name or self.db_name
        user = user or self.db_user
        password = password or self.db_password
        
        return f"postgresql://{user}:{password}@{host}:{port}/{name}"
    
    def create_engine(self, use_read_replica: bool = False, **kwargs) -> Engine:
        """
        Tạo SQLAlchemy engine với connection pooling được tối ưu
        
        Args:
            use_read_replica: Nếu True, sử dụng read replica (cho read-only queries)
            **kwargs: Override các tham số pool nếu cần
        """
        if use_read_replica and self.read_replica_host:
            # Sử dụng read replica
            database_url = self._build_database_url(
                host=self.read_replica_host,
                port=self.read_replica_port,
                name=self.read_replica_name,
                user=self.read_replica_user,
                password=self.read_replica_password
            )
            logger.info(f"Using read replica: {self.read_replica_host}:{self.read_replica_port}")
        else:
            # Sử dụng primary database
            database_url = self._build_database_url()
        
        # Pool configuration
        pool_size = kwargs.get("pool_size", self.pool_size)
        max_overflow = kwargs.get("max_overflow", self.max_overflow)
        pool_recycle = kwargs.get("pool_recycle", self.pool_recycle)
        pool_timeout = kwargs.get("pool_timeout", self.pool_timeout)
        pool_pre_ping = kwargs.get("pool_pre_ping", self.pool_pre_ping)
        
        # Tạo engine với connection pooling
        engine = create_engine(
            database_url,
            poolclass=QueuePool,
            pool_size=pool_size,
            max_overflow=max_overflow,
            pool_recycle=pool_recycle,
            pool_timeout=pool_timeout,
            pool_pre_ping=pool_pre_ping,
            echo=False,  # Set True để debug SQL queries
            connect_args=self._build_connect_args(),
            **{k: v for k, v in kwargs.items() if k not in [
                "pool_size", "max_overflow", "pool_recycle", 
                "pool_timeout", "pool_pre_ping"
            ]}
        )
        
        logger.debug(
            f"Created engine with pool_size={pool_size}, "
            f"max_overflow={max_overflow}, pool_recycle={pool_recycle}s"
        )
        
        return engine
    
    def get_pool_stats(self, engine: Engine) -> Dict[str, Any]:
        """Lấy thống kê về connection pool"""
        pool = engine.pool
        stats = {
            "size": pool.size(),
            "checked_in": pool.checkedin(),
            "checked_out": pool.checkedout(),
            "overflow": pool.overflow()
        }
        
        # Thử lấy invalid count nếu có (không phải tất cả pool types đều có)
        try:
            if hasattr(pool, 'invalid'):
                stats["invalid"] = pool.invalid()
            else:
                stats["invalid"] = 0
        except (AttributeError, TypeError):
            stats["invalid"] = 0
        
        return stats
    
    def has_read_replica(self) -> bool:
        """Kiểm tra xem có read replica được cấu hình không"""
        return self.read_replica_host is not None and self.read_replica_host != ""


# Singleton instance
_db_config = None


def get_database_config() -> DatabaseConfig:
    """Lấy singleton instance của DatabaseConfig"""
    global _db_config
    if _db_config is None:
        _db_config = DatabaseConfig()
    return _db_config