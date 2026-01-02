"""
Application configuration and database setup.
This module contains all configuration logic and database initialization
for the FastAPI application.
"""
import os
import logging
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import sessionmaker
from contextlib import asynccontextmanager
from dotenv import load_dotenv

# Import LLM service for lifespan
from services.llm_service import llm_service

# Load environment variables
load_dotenv()

# Check if pgvector is available
USE_PGVECTOR = os.getenv("USE_PGVECTOR", "false").lower() == "true"
try:
    from pgvector.sqlalchemy import Vector
    PGVECTOR_AVAILABLE = True
except ImportError:
    PGVECTOR_AVAILABLE = False
    Vector = None
    if USE_PGVECTOR:
        logging.warning("pgvector not installed. Install with: pip install pgvector. Falling back to JSON text storage.")

# CORS configuration
# Cho phép cấu hình CORS origins qua biến môi trường
# Format: CORS_ORIGINS=http://localhost:8000,http://localhost:3000,https://yourdomain.com
CORS_ORIGINS_ENV = os.getenv("CORS_ORIGINS", "")
if CORS_ORIGINS_ENV:
    # Parse từ env variable (comma-separated)
    ALLOWED_ORIGINS = [origin.strip() for origin in CORS_ORIGINS_ENV.split(",") if origin.strip()]
else:
    # Default: chỉ cho phép localhost cho development
    ALLOWED_ORIGINS = [
        "http://localhost:8000",
        "http://localhost:3000",
        "http://127.0.0.1:8000",
        "http://127.0.0.1:3000",
    ]

# Database configuration
# JDBC URL: jdbc:postgresql://192.168.0.106:5432/ai_system
# Convert to Python format: postgresql://user:password@host:port/database
DB_HOST = os.getenv("DB_HOST", "192.168.0.106")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "ai_system")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")

# TLS/SSL configuration for database
DB_SSL_MODE = os.getenv("DB_SSL_MODE", "prefer")  # disable, allow, prefer, require, verify-ca, verify-full
DB_SSL_ROOT_CERT = os.getenv("DB_SSL_ROOT_CERT", None)  # Path to CA certificate
DB_SSL_CERT = os.getenv("DB_SSL_CERT", None)  # Path to client certificate
DB_SSL_KEY = os.getenv("DB_SSL_KEY", None)  # Path to client key

# Build database URL with SSL parameters
DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# SSL connection arguments for SQLAlchemy
DB_CONNECT_ARGS = {
    "connect_timeout": 10,
    "sslmode": DB_SSL_MODE
}

# Add SSL certificates if provided
if DB_SSL_ROOT_CERT:
    DB_CONNECT_ARGS["sslrootcert"] = DB_SSL_ROOT_CERT
if DB_SSL_CERT:
    DB_CONNECT_ARGS["sslcert"] = DB_SSL_CERT
if DB_SSL_KEY:
    DB_CONNECT_ARGS["sslkey"] = DB_SSL_KEY


def sanitize_database_url(url: str) -> str:
    """
    Sanitize database URL để loại bỏ password khi log
    Thay password bằng '***' để bảo mật
    """
    try:
        from urllib.parse import urlparse, urlunparse
        
        parsed = urlparse(url)
        # Giữ nguyên scheme, netloc (nhưng mask password), path, params, fragment
        # Chỉ thay đổi phần password trong netloc
        if parsed.password:
            # Thay password bằng ***
            netloc = parsed.netloc.replace(f":{parsed.password}@", ":***@")
        else:
            netloc = parsed.netloc
        
        sanitized = urlunparse((
            parsed.scheme,
            netloc,
            parsed.path,
            parsed.params,
            parsed.query,
            parsed.fragment
        ))
        return sanitized
    except Exception:
        # Nếu có lỗi, trả về safe version
        return url.split("@")[0] + "@***" if "@" in url else "***"


# Logging: structured logging với JSON format (nếu cần)
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_FORMAT = os.getenv("LOG_FORMAT", "standard")  # standard hoặc json

if LOG_FORMAT == "json":
    import json
    from datetime import datetime
    
    class JSONFormatter(logging.Formatter):
        def format(self, record):
            log_data = {
                "timestamp": datetime.utcnow().isoformat(),
                "level": record.levelname,
                "logger": record.name,
                "message": record.getMessage(),
                "module": record.module,
                "function": record.funcName,
                "line": record.lineno
            }
            if record.exc_info:
                log_data["exception"] = self.formatException(record.exc_info)
            return json.dumps(log_data)
    
    handler = logging.StreamHandler()
    handler.setFormatter(JSONFormatter())
    logging.basicConfig(level=getattr(logging, LOG_LEVEL), handlers=[handler])
else:
    # Standard logging format
    logging.basicConfig(
        level=getattr(logging, LOG_LEVEL),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

# Import database configuration module
from services.database_config import get_database_config
from services.async_database_config import get_async_database_config

# Create database engine với connection pooling configuration được tối ưu
db_config = get_database_config()
engine = db_config.create_engine()

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create async database engine và session factory
async_db_config = get_async_database_config()
async_engine = async_db_config.create_async_engine()
AsyncSessionLocal = async_db_config.create_async_session_factory(async_engine)


def index_exists(conn, table_name: str, index_name: str) -> bool:
    """Kiểm tra xem index đã tồn tại chưa"""
    result = conn.execute(text("""
        SELECT EXISTS (
            SELECT 1 
            FROM pg_indexes 
            WHERE tablename = :table_name 
            AND indexname = :index_name
        )
    """), {"table_name": table_name, "index_name": index_name})
    return result.scalar()


def table_exists(conn, table_name: str) -> bool:
    """Kiểm tra xem table đã tồn tại chưa"""
    result = conn.execute(text("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_name = :table_name
        )
    """), {"table_name": table_name})
    return result.scalar()


def setup_cache_entries_table():
    """
    Tự động tạo bảng cache_entries cho L3 cache
    Chạy khi ứng dụng khởi động nếu AUTO_MIGRATE_CACHE_TABLE=true (default: true)
    """
    auto_migrate = os.getenv("AUTO_MIGRATE_CACHE_TABLE", "true").lower() == "true"
    if not auto_migrate:
        logging.info("⏭️  Auto-migrate cache_entries table disabled (AUTO_MIGRATE_CACHE_TABLE=false)")
        return
    
    try:
        with engine.connect() as conn:
            # Check if table exists
            if table_exists(conn, "cache_entries"):
                logging.debug("⏭️  Table cache_entries đã tồn tại, bỏ qua")
                return
            
            # Create table
            create_table = text("""
                CREATE TABLE cache_entries (
                    id SERIAL PRIMARY KEY,
                    cache_key VARCHAR(512) UNIQUE NOT NULL,
                    cache_value TEXT NOT NULL,
                    cache_type VARCHAR(50) NOT NULL,
                    expires_at TIMESTAMP NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    access_count INTEGER DEFAULT 0,
                    last_accessed TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            conn.execute(create_table)
            conn.commit()
            logging.info("✅ Đã tạo bảng cache_entries cho L3 cache")
            
            # Create indexes
            indexes_to_create = [
                {
                    "name": "idx_cache_entries_key",
                    "table": "cache_entries",
                    "columns": "cache_key",
                    "description": "Index cho cache_key để lookup nhanh"
                },
                {
                    "name": "idx_cache_entries_type",
                    "table": "cache_entries",
                    "columns": "cache_type",
                    "description": "Index cho cache_type để filter theo loại cache"
                },
                {
                    "name": "idx_cache_entries_expires",
                    "table": "cache_entries",
                    "columns": "expires_at",
                    "description": "Index cho expires_at để cleanup expired entries"
                },
                {
                    "name": "idx_cache_entries_access_count",
                    "table": "cache_entries",
                    "columns": "access_count",
                    "description": "Index cho access_count để cache warming"
                },
                {
                    "name": "idx_cache_entries_last_accessed",
                    "table": "cache_entries",
                    "columns": "last_accessed",
                    "description": "Index cho last_accessed để cache warming"
                },
            ]
            
            created_indexes = 0
            for idx in indexes_to_create:
                try:
                    if index_exists(conn, idx["table"], idx["name"]):
                        logging.debug(f"⏭️  Index {idx['name']} đã tồn tại, bỏ qua")
                        continue
                    
                    create_index_sql = text(f"""
                        CREATE INDEX {idx['name']} 
                        ON {idx['table']} ({idx['columns']})
                    """)
                    
                    conn.execute(create_index_sql)
                    conn.commit()
                    logging.info(f"✅ Đã tạo index: {idx['name']} trên {idx['table']}({idx['columns']})")
                    created_indexes += 1
                except Exception as e:
                    logging.error(f"❌ Lỗi khi tạo index {idx['name']}: {e}")
                    conn.rollback()
            
            if created_indexes > 0:
                logging.info(f"📊 Cache table indexes: ✅ Đã tạo {created_indexes} indexes")
                
                # Analyze table để PostgreSQL cập nhật statistics
                logging.info("🔄 Đang chạy ANALYZE cache_entries để cập nhật statistics...")
                try:
                    conn.execute(text("ANALYZE cache_entries"))
                    conn.commit()
                except Exception as e:
                    logging.warning(f"⚠️  Không thể analyze bảng cache_entries: {e}")
    
    except Exception as e:
        logging.error(f"❌ Lỗi khi setup cache_entries table: {e}")
        # Không raise exception để app vẫn có thể khởi động nếu table không thể tạo


def setup_database_indexes():
    """
    Tự động tạo các indexes cần thiết cho query optimization
    Chạy khi ứng dụng khởi động nếu AUTO_MIGRATE_INDEXES=true (default: true)
    """
    auto_migrate = os.getenv("AUTO_MIGRATE_INDEXES", "true").lower() == "true"
    if not auto_migrate:
        logging.info("⏭️  Auto-migrate indexes disabled (AUTO_MIGRATE_INDEXES=false)")
        return
    
    indexes_to_create = [
        # Indexes cho agent_conversations
        {
            "name": "idx_agent_conversations_session_id",
            "table": "agent_conversations",
            "columns": "session_id",
            "description": "Index cho session_id để query conversations theo session nhanh hơn"
        },
        {
            "name": "idx_agent_conversations_created_at",
            "table": "agent_conversations",
            "columns": "created_at",
            "description": "Index cho created_at để sort và filter theo thời gian nhanh hơn"
        },
        {
            "name": "idx_agent_conversations_session_created",
            "table": "agent_conversations",
            "columns": "session_id, created_at",
            "description": "Composite index cho session_id và created_at (thường query cùng lúc)"
        },
        
        # Indexes cho conversation_feedback
        {
            "name": "idx_conversation_feedback_conversation_id",
            "table": "conversation_feedback",
            "columns": "conversation_id",
            "description": "Index cho conversation_id để join và filter feedback theo conversation"
        },
        {
            "name": "idx_conversation_feedback_rating",
            "table": "conversation_feedback",
            "columns": "rating",
            "description": "Index cho rating để filter feedback theo rating nhanh hơn"
        },
        {
            "name": "idx_conversation_feedback_conv_rating",
            "table": "conversation_feedback",
            "columns": "conversation_id, rating",
            "description": "Composite index cho conversation_id và rating (thường filter cùng lúc)"
        },
        
        # Indexes cho conversation_embeddings
        {
            "name": "idx_conversation_embeddings_conversation_id",
            "table": "conversation_embeddings",
            "columns": "conversation_id",
            "description": "Index cho conversation_id để join embeddings với conversations nhanh hơn"
        },
    ]
    
    try:
        with engine.connect() as conn:
            created_count = 0
            skipped_count = 0
            
            for idx in indexes_to_create:
                try:
                    # Kiểm tra xem index đã tồn tại chưa
                    if index_exists(conn, idx["table"], idx["name"]):
                        logging.debug(f"⏭️  Index {idx['name']} đã tồn tại, bỏ qua")
                        skipped_count += 1
                        continue
                    
                    # Kiểm tra xem bảng có tồn tại không
                    if idx["table"] not in inspect(engine).get_table_names():
                        logging.warning(f"⚠️  Bảng {idx['table']} không tồn tại, bỏ qua index {idx['name']}")
                        skipped_count += 1
                        continue
                    
                    # Tạo index
                    create_sql = f"""
                        CREATE INDEX {idx['name']} 
                        ON {idx['table']} ({idx['columns']})
                    """
                    
                    conn.execute(text(create_sql))
                    conn.commit()
                    
                    logging.info(f"✅ Đã tạo index: {idx['name']} trên {idx['table']}({idx['columns']})")
                    created_count += 1
                    
                except Exception as e:
                    logging.error(f"❌ Lỗi khi tạo index {idx['name']}: {e}")
                    conn.rollback()
            
            if created_count > 0 or skipped_count > 0:
                logging.info(f"📊 Database indexes: ✅ Đã tạo {created_count}, ⏭️  Đã bỏ qua {skipped_count}")
            
            # Analyze tables để PostgreSQL cập nhật statistics
            if created_count > 0:
                logging.info("🔄 Đang chạy ANALYZE để cập nhật statistics...")
                for idx in indexes_to_create:
                    try:
                        conn.execute(text(f"ANALYZE {idx['table']}"))
                    except Exception as e:
                        logging.warning(f"⚠️  Không thể analyze bảng {idx['table']}: {e}")
                conn.commit()
    
    except Exception as e:
        logging.error(f"❌ Lỗi khi setup database indexes: {e}")
        # Không raise exception để app vẫn có thể khởi động nếu indexes không thể tạo

# Import models from models.py to avoid circular imports
from .models import (
    Base, AgentTask, AgentConversation, ConversationFeedback, 
    ConversationEmbedding, APIKey, APIKeyAuditLog, CacheEntry
)

# Create tables
Base.metadata.create_all(bind=engine)

# Import Pydantic models from separate module for better organization
# Re-export for backward compatibility
from .pydantic_models import (
    TaskCreate,
    TaskResponse,
    ConversationCreate,
    ConversationResponse,
    FeedbackCreate,
    FeedbackResponse,
    FeedbackStats,
)

# Lifespan event handler (thay thế on_event deprecated)
@asynccontextmanager
async def lifespan(app):
    # Startup
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logging.info("Database connection: OK")
        
        # Setup database indexes tự động
        setup_database_indexes()
        
        # Setup cache_entries table tự động
        setup_cache_entries_table()
        
        # Check Ollama connection
        ollama_status = await llm_service.check_ollama_connection()
        if ollama_status.get("connected"):
            exact_model = ollama_status.get("exact_model", llm_service.model_name)
            logging.info(f"Ollama connection: OK - Model: {exact_model}")
            if not ollama_status.get("model_available"):
                available_models = ollama_status.get('models', [])
                logging.warning(f"Model '{llm_service.model_name}' not found in Ollama. Available models: {available_models}")
                # Gợi ý model name đúng
                if available_models:
                    suggested_model = available_models[0]
                    logging.info(f"Gợi ý: Sử dụng model '{suggested_model}' (cập nhật LLM_MODEL_NAME trong .env)")
        else:
            logging.warning(f"Ollama connection failed: {ollama_status.get('error', 'Unknown error')}")
        
        # Start background tasks
        from services.background_tasks import background_tasks_service
        await background_tasks_service.start()
        logging.info("Background tasks started")
        
        # Initialize cache service để test Redis connection khi app start
        try:
            from services.advanced_cache_service import get_advanced_cache_service
            cache_service = get_advanced_cache_service()
            if cache_service.l2_enabled:
                logging.info("Redis cache service initialized and connected")
            else:
                logging.debug("Cache service initialized (Redis not available or disabled)")
        except Exception as e:
            logging.debug(f"Cache service initialization skipped: {e}")
        
        # Start embedding precompute task nếu được bật
        try:
            from services.embedding_service import embedding_service
            if embedding_service.precompute_enabled:
                precompute_interval = int(os.getenv("EMBEDDING_PRECOMPUTE_INTERVAL", "3600"))  # Default: 1 hour
                await embedding_service.start_precompute_task(precompute_interval)
                logging.info(f"Embedding precompute task started (interval: {precompute_interval}s)")
        except Exception as e:
            logging.debug(f"Embedding precompute task initialization skipped: {e}")
        
        # Start Celery worker nếu ENABLE_CELERY_WORKER=true
        enable_celery_worker = os.getenv("ENABLE_CELERY_WORKER", "false").lower() == "true"
        if enable_celery_worker:
            try:
                from services.celery_worker_manager import start_celery_worker
                start_celery_worker()
                logging.info("✅ Celery worker integrated and started")
            except Exception as e:
                logging.warning(f"⚠️  Failed to start integrated Celery worker: {e}")
                logging.info("💡 You can still use external Celery worker with: celery -A services.celery_config worker")
    except Exception as exc:
        # Không log exception trực tiếp vì có thể chứa password
        # Chỉ log error message an toàn
        error_msg = str(exc)
        # Loại bỏ password nếu có trong error message
        if "password" in error_msg.lower() or "@" in error_msg or "postgresql://" in error_msg:
            error_msg = "Database connection failed. Please check database configuration."
        logging.error("Database connection failed: %s", error_msg)
        # Log sanitized database URL để debug (không có password)
        logging.debug("Database URL (sanitized): %s", sanitize_database_url(DATABASE_URL))
    
    yield
    
    # Shutdown
    try:
        from services.background_tasks import background_tasks_service
        await background_tasks_service.stop()
        logging.info("Background tasks stopped")
    except Exception as e:
        logging.debug(f"Error stopping background tasks: {e}")
    
    try:
        from services.embedding_service import embedding_service
        embedding_service.stop_precompute_task()
        logging.info("Embedding precompute task stopped")
    except Exception as e:
        logging.debug(f"Error stopping embedding precompute task: {e}")
        logging.error(f"Error stopping background tasks: {e}")
    
    # Stop Celery worker nếu đang chạy (chạy trong finally để đảm bảo luôn được gọi)
    try:
        from services.celery_worker_manager import stop_celery_worker
        stop_celery_worker()
    except Exception as e:
        logging.error(f"Error stopping Celery worker: {e}")