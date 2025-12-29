from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from pydantic import BaseModel, ConfigDict, field_validator
from datetime import datetime
from typing import Optional, List, Dict
from contextlib import asynccontextmanager
import os
import importlib
import logging
from dotenv import load_dotenv

# Input validation & security helpers
from middleware.security import (
    validate_and_sanitize_text,
    sanitize_text,
    MAX_MESSAGE_LENGTH,
    MAX_TASK_NAME_LENGTH,
    MAX_COMMENT_LENGTH,
    MAX_SESSION_ID_LENGTH,
    InputSizeLimitMiddleware,
)

# Import rate limiting
from middleware.rate_limit import limiter, limiter_with_api_key, rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

# Import metrics
from middleware.metrics_middleware import MetricsMiddleware
from services.metrics_service import metrics_service, get_metrics_export

# Import LLM and Fine-tuning services
from services.llm_service import llm_service
from services.fine_tuning_service import FineTuningService
from services.feedback_service import FeedbackService

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
        from urllib.parse import urlparse, urlunparse, parse_qs, urlencode
        
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

# Create database engine với connection pooling configuration và SSL
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,  # Kiểm tra connection trước khi sử dụng
    pool_size=10,  # Số lượng connections trong pool
    max_overflow=20,  # Số lượng connections có thể vượt quá pool_size
    pool_recycle=3600,  # Recycle connections sau 1 giờ
    pool_timeout=30,  # Timeout khi lấy connection từ pool
    echo=False,  # Không log SQL queries
    # SSL/TLS configuration và connection timeout
    connect_args=DB_CONNECT_ARGS
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Import models from models.py to avoid circular imports
from models import (
    Base, AgentTask, AgentConversation, ConversationFeedback, 
    ConversationEmbedding, APIKey, APIKeyAuditLog
)

# Create tables
Base.metadata.create_all(bind=engine)

# Pydantic Models
class TaskCreate(BaseModel):
    task_name: str
    description: Optional[str] = None

    model_config = ConfigDict(str_strip_whitespace=True)

    @field_validator("task_name")
    @classmethod
    def validate_task_name(cls, v: str) -> str:
        return validate_and_sanitize_text(
            v,
            max_length=MAX_TASK_NAME_LENGTH,
            field_name="task_name",
            allow_empty=False,
        )

    @field_validator("description")
    @classmethod
    def validate_description(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        return validate_and_sanitize_text(
            v,
            max_length=MAX_COMMENT_LENGTH,
            field_name="description",
            allow_empty=True,
        )

class TaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    task_name: str
    description: Optional[str]
    status: str
    result: Optional[str]
    created_at: datetime
    updated_at: datetime

class ConversationCreate(BaseModel):
    user_message: str
    session_id: Optional[str] = None

    model_config = ConfigDict(str_strip_whitespace=True)

    @field_validator("user_message")
    @classmethod
    def validate_user_message(cls, v: str) -> str:
        return validate_and_sanitize_text(
            v,
            max_length=MAX_MESSAGE_LENGTH,
            field_name="user_message",
            allow_empty=False,
        )

    @field_validator("session_id")
    @classmethod
    def validate_session_id(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        return validate_and_sanitize_text(
            v,
            max_length=MAX_SESSION_ID_LENGTH,
            field_name="session_id",
            allow_empty=False,
        )

class ConversationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    user_message: str
    ai_response: Optional[str]
    session_id: Optional[str]
    created_at: datetime

class FeedbackCreate(BaseModel):
    conversation_id: int
    rating: Optional[int] = None  # 1-5 stars
    feedback_type: str = "rating"  # rating, thumbs_up, thumbs_down, detailed
    comment: Optional[str] = None
    user_correction: Optional[str] = None  # Câu trả lời đúng nếu user muốn sửa
    is_helpful: Optional[str] = None  # yes, no, partially

    model_config = ConfigDict(str_strip_whitespace=True)

    @field_validator("rating")
    @classmethod
    def validate_rating(cls, v: Optional[int]) -> Optional[int]:
        if v is None:
            return v
        if v < 1 or v > 5:
            raise ValueError("rating must be between 1 and 5")
        return v

    @field_validator("feedback_type")
    @classmethod
    def validate_feedback_type(cls, v: str) -> str:
        allowed = {"rating", "thumbs_up", "thumbs_down", "detailed"}
        if v not in allowed:
            raise ValueError(f"feedback_type must be one of {sorted(allowed)}")
        return v

    @field_validator("is_helpful")
    @classmethod
    def validate_is_helpful(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        allowed = {"yes", "no", "partially"}
        if v not in allowed:
            raise ValueError(f"is_helpful must be one of {sorted(allowed)}")
        return v

    @field_validator("comment")
    @classmethod
    def validate_comment(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        return validate_and_sanitize_text(
            v,
            max_length=MAX_COMMENT_LENGTH,
            field_name="comment",
            allow_empty=True,
        )

    @field_validator("user_correction")
    @classmethod
    def validate_user_correction(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        return validate_and_sanitize_text(
            v,
            max_length=MAX_MESSAGE_LENGTH,
            field_name="user_correction",
            allow_empty=False,
        )

class FeedbackResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    conversation_id: int
    rating: Optional[int]
    feedback_type: str
    comment: Optional[str]
    user_correction: Optional[str]
    is_helpful: Optional[str]
    created_at: datetime
    updated_at: datetime

class FeedbackStats(BaseModel):
    total_feedback: int
    average_rating: Optional[float]
    positive_count: int
    negative_count: int
    neutral_count: int
    helpful_count: int
    not_helpful_count: int
    feedback_by_type: Dict[str, int]

# Lifespan event handler (thay thế on_event deprecated)
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logging.info("Database connection: OK")
        
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
        logging.error(f"Error stopping background tasks: {e}")

# FastAPI app
app = FastAPI(
    title="AI Agent Server",
    description="AI Agent Server với PostgreSQL Database",
    version="1.0.0",
    lifespan=lifespan
)

# Attach rate limiter to app
app.state.limiter = limiter_with_api_key
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

# Security headers middleware (add first to enforce HTTPS and add headers)
from middleware.security_headers import SecurityHeadersMiddleware
app.add_middleware(SecurityHeadersMiddleware)

# Secure logging middleware (mask sensitive data in logs)
from middleware.logging_middleware import SecureLoggingMiddleware
app.add_middleware(SecureLoggingMiddleware)

# Input size limiting middleware (protect against very large request bodies)
app.add_middleware(InputSizeLimitMiddleware)

# API Key middleware (add early to set up request state)
from middleware.api_key_middleware import APIKeyMiddleware
app.add_middleware(APIKeyMiddleware, session_factory=SessionLocal)

# Metrics middleware (add before CORS to track all requests)
app.add_middleware(MetricsMiddleware)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,  # Chỉ cho phép các origins đã cấu hình
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Dependency to get database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Metrics endpoint for Prometheus
@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint"""
    try:
        metrics_data, content_type = get_metrics_export()
        if metrics_data:
            from fastapi.responses import Response
            return Response(content=metrics_data, media_type=content_type)
        else:
            return {"message": "Metrics not available"}
    except Exception as e:
        logging.error(f"Error generating metrics: {e}")
        return {"error": "Failed to generate metrics"}

# Health check endpoint
@app.get("/")
async def root():
    return {
        "message": "AI Agent Server đang chạy",
        "database": "PostgreSQL",
        "status": "active"
    }

@app.get("/health")
async def health_check(db: Session = Depends(get_db)):
    try:
        # Test database connection
        db.execute(text("SELECT 1"))
        
        # Check Ollama connection
        ollama_status = await llm_service.check_ollama_connection()
        
        return {
            "status": "healthy",
            "database": "connected",
            "llm": {
                "provider": llm_service.provider,
                "model": llm_service.model_name,
                "ollama_connected": ollama_status.get("connected", False),
                "model_available": ollama_status.get("model_available", False)
            }
        }
    except Exception as e:
        # Không expose database connection details trong error message
        error_msg = str(e)
        # Sanitize error message để không leak password
        if "password" in error_msg.lower() or "@" in error_msg or "postgresql://" in error_msg:
            error_msg = "Database connection failed"
        raise HTTPException(status_code=503, detail=error_msg)

# Include routes from routes package (lazy import to avoid circular import)
def _register_routes():
    """Lazy import routes to avoid circular import"""
    from routes.routes import router
    from routes.routes_analysis import router as analysis_router
    from routes.api_keys import router as api_keys_router
    app.include_router(router)
    app.include_router(analysis_router)
    app.include_router(api_keys_router)

_register_routes()

if __name__ == "__main__":
    # Lazy import to avoid linter complaints when uvicorn is not installed in the active editor interpreter
    uvicorn = importlib.import_module("uvicorn")
    uvicorn.run(app, host="0.0.0.0", port=8000)