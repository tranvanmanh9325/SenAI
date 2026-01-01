"""
Async Database Configuration Module
Cung cấp cấu hình async database với async SQLAlchemy và asyncpg driver
"""
import os
import logging
from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import text

logger = logging.getLogger(__name__)


class AsyncDatabaseConfig:
    """Quản lý cấu hình async database connection pooling"""
    
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
        self.pool_size = int(os.getenv("DB_POOL_SIZE", "10"))
        self.max_overflow = int(os.getenv("DB_MAX_OVERFLOW", "20"))
        self.pool_recycle = int(os.getenv("DB_POOL_RECYCLE", "3600"))
        self.pool_timeout = int(os.getenv("DB_POOL_TIMEOUT", "30"))
        self.pool_pre_ping = os.getenv("DB_POOL_PRE_PING", "true").lower() == "true"
        
        # Read replica configuration
        self.read_replica_host = os.getenv("DB_READ_REPLICA_HOST", None)
        self.read_replica_port = os.getenv("DB_READ_REPLICA_PORT", self.db_port)
        self.read_replica_name = os.getenv("DB_READ_REPLICA_NAME", self.db_name)
        self.read_replica_user = os.getenv("DB_READ_REPLICA_USER", self.db_user)
        self.read_replica_password = os.getenv("DB_READ_REPLICA_PASSWORD", self.db_password)
        
        # Connection timeout
        self.connect_timeout = int(os.getenv("DB_CONNECT_TIMEOUT", "10"))
        
        # Statement timeout (milliseconds)
        self.statement_timeout = os.getenv("DB_STATEMENT_TIMEOUT", None)
        
        # Application name
        self.application_name = os.getenv("DB_APPLICATION_NAME", "ai_agent_backend_async")
    
    def _build_connect_args(self) -> Dict[str, Any]:
        """Xây dựng connection arguments cho asyncpg"""
        connect_args = {
            "command_timeout": self.connect_timeout,
            "server_settings": {
                "application_name": self.application_name,
            }
        }
        
        # SSL configuration
        if self.db_ssl_mode and self.db_ssl_mode != "disable":
            ssl_config = {}
            if self.db_ssl_root_cert:
                ssl_config["sslrootcert"] = self.db_ssl_root_cert
            if self.db_ssl_cert:
                ssl_config["sslcert"] = self.db_ssl_cert
            if self.db_ssl_key:
                ssl_config["sslkey"] = self.db_ssl_key
            if ssl_config:
                connect_args["ssl"] = ssl_config
        
        # Statement timeout
        if self.statement_timeout:
            connect_args["server_settings"]["statement_timeout"] = self.statement_timeout
        
        return connect_args
    
    def _build_database_url(self, host: Optional[str] = None, port: Optional[str] = None,
                           name: Optional[str] = None, user: Optional[str] = None,
                           password: Optional[str] = None) -> str:
        """Xây dựng async database URL (postgresql+asyncpg://)"""
        host = host or self.db_host
        port = port or self.db_port
        name = name or self.db_name
        user = user or self.db_user
        password = password or self.db_password
        
        # Use postgresql+asyncpg:// for async SQLAlchemy
        return f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{name}"
    
    def create_async_engine(self, use_read_replica: bool = False, **kwargs):
        """
        Tạo async SQLAlchemy engine với connection pooling được tối ưu
        
        Args:
            use_read_replica: Nếu True, sử dụng read replica (cho read-only queries)
            **kwargs: Override các tham số pool nếu cần
        """
        if use_read_replica and self.read_replica_host:
            database_url = self._build_database_url(
                host=self.read_replica_host,
                port=self.read_replica_port,
                name=self.read_replica_name,
                user=self.read_replica_user,
                password=self.read_replica_password
            )
            logger.info(f"Using async read replica: {self.read_replica_host}:{self.read_replica_port}")
        else:
            database_url = self._build_database_url()
        
        # Pool configuration
        pool_size = kwargs.get("pool_size", self.pool_size)
        max_overflow = kwargs.get("max_overflow", self.max_overflow)
        pool_recycle = kwargs.get("pool_recycle", self.pool_recycle)
        pool_timeout = kwargs.get("pool_timeout", self.pool_timeout)
        pool_pre_ping = kwargs.get("pool_pre_ping", self.pool_pre_ping)
        
        # Tạo async engine với connection pooling
        # Note: async engine tự động sử dụng AsyncAdaptedQueuePool, không cần chỉ định poolclass
        engine = create_async_engine(
            database_url,
            pool_size=pool_size,
            max_overflow=max_overflow,
            pool_recycle=pool_recycle,
            pool_pre_ping=pool_pre_ping,
            echo=False,  # Set True để debug SQL queries
            connect_args=self._build_connect_args(),
            **{k: v for k, v in kwargs.items() if k not in [
                "pool_size", "max_overflow", "pool_recycle", 
                "pool_timeout", "pool_pre_ping"
            ]}
        )
        
        logger.info(
            f"Created async engine with pool_size={pool_size}, "
            f"max_overflow={max_overflow}, pool_recycle={pool_recycle}s"
        )
        
        return engine
    
    def create_async_session_factory(self, engine):
        """Tạo async session factory"""
        return async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False
        )
    
    async def get_pool_stats(self, engine) -> Dict[str, Any]:
        """Lấy thống kê về connection pool"""
        pool = engine.pool
        stats = {
            "size": pool.size(),
            "checked_in": pool.checkedin(),
            "checked_out": pool.checkedout(),
            "overflow": pool.overflow()
        }
        
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
_async_db_config = None


def get_async_database_config() -> AsyncDatabaseConfig:
    """Lấy singleton instance của AsyncDatabaseConfig"""
    global _async_db_config
    if _async_db_config is None:
        _async_db_config = AsyncDatabaseConfig()
    return _async_db_config


