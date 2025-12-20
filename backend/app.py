from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text, text
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional, List, Dict
from contextlib import asynccontextmanager
import os
import importlib
import logging
from dotenv import load_dotenv

# Import rate limiting
from rate_limit import limiter, limiter_with_api_key, rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

# Import LLM and Fine-tuning services
from llm_service import llm_service
from fine_tuning_service import FineTuningService
from feedback_service import FeedbackService

# Load environment variables
load_dotenv()

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

DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"


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


# Logging: keep output minimal, silence noisy SQL logs
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

# Create database engine với connection pooling configuration
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,  # Kiểm tra connection trước khi sử dụng
    pool_size=10,  # Số lượng connections trong pool
    max_overflow=20,  # Số lượng connections có thể vượt quá pool_size
    pool_recycle=3600,  # Recycle connections sau 1 giờ
    pool_timeout=30,  # Timeout khi lấy connection từ pool
    echo=False,  # Không log SQL queries
    # Ẩn password trong SQLAlchemy logs
    connect_args={"connect_timeout": 10}
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for models
Base = declarative_base()

# Database Models
class AgentTask(Base):
    __tablename__ = "agent_tasks"
    
    id = Column(Integer, primary_key=True, index=True)
    task_name = Column(String(255), nullable=False)
    description = Column(Text)
    status = Column(String(50), default="pending")
    result = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class AgentConversation(Base):
    __tablename__ = "agent_conversations"
    
    id = Column(Integer, primary_key=True, index=True)
    user_message = Column(Text, nullable=False)
    ai_response = Column(Text)
    session_id = Column(String(255))
    created_at = Column(DateTime, default=datetime.utcnow)

class ConversationFeedback(Base):
    __tablename__ = "conversation_feedback"
    
    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, nullable=False, index=True)
    rating = Column(Integer, nullable=False)  # 1-5 stars, hoặc -1 (thumbs down), 1 (thumbs up)
    feedback_type = Column(String(50), default="rating")  # rating, thumbs_up, thumbs_down, detailed
    comment = Column(Text)  # Comment chi tiết từ user
    user_correction = Column(Text)  # Câu trả lời đúng nếu user sửa
    is_helpful = Column(String(10))  # yes, no, partially
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class ConversationEmbedding(Base):
    __tablename__ = "conversation_embeddings"
    
    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, nullable=False, unique=True, index=True)
    user_message_embedding = Column(Text)  # JSON array của embedding vector
    ai_response_embedding = Column(Text)  # JSON array của embedding vector
    combined_embedding = Column(Text)  # JSON array của combined embedding
    embedding_model = Column(String(100), default="sentence-transformers")  # Model đã dùng
    embedding_dimension = Column(Integer, default=384)  # Dimension của embedding
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

# Create tables
Base.metadata.create_all(bind=engine)

# Pydantic Models
class TaskCreate(BaseModel):
    task_name: str
    description: Optional[str] = None

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
    
    # Shutdown (nếu cần cleanup)
    pass

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

# Include routes from routes.py (lazy import to avoid circular import)
def _register_routes():
    """Lazy import routes to avoid circular import"""
    from routes import router
    app.include_router(router)

_register_routes()

if __name__ == "__main__":
    # Lazy import to avoid linter complaints when uvicorn is not installed in the active editor interpreter
    uvicorn = importlib.import_module("uvicorn")
    uvicorn.run(app, host="0.0.0.0", port=8000)