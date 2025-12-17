from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text, text
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional, List
import os
import importlib
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Database configuration
# JDBC URL: jdbc:postgresql://192.168.0.106:5432/ai_system
# Convert to Python format: postgresql://user:password@host:port/database
DB_HOST = os.getenv("DB_HOST", "192.168.0.106")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "ai_system")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")

DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# Logging: keep output minimal, silence noisy SQL logs
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

# Create database engine
engine = create_engine(DATABASE_URL, pool_pre_ping=True, echo=False)

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

# FastAPI app
app = FastAPI(
    title="AI Agent Server",
    description="AI Agent Server với PostgreSQL Database",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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

# Startup hook: verify DB connectivity once, log concise status
@app.on_event("startup")
def startup_check_db():
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logging.info("Database connection: OK")
    except Exception as exc:
        logging.error("Database connection failed: %s", exc)

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
        return {
            "status": "healthy",
            "database": "connected"
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Database connection failed: {str(e)}")

# Task endpoints
@app.post("/tasks", response_model=TaskResponse)
async def create_task(task: TaskCreate, db: Session = Depends(get_db)):
    db_task = AgentTask(
        task_name=task.task_name,
        description=task.description,
        status="pending"
    )
    db.add(db_task)
    db.commit()
    db.refresh(db_task)
    return db_task

@app.get("/tasks", response_model=List[TaskResponse])
async def get_tasks(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    tasks = db.query(AgentTask).offset(skip).limit(limit).all()
    return tasks

@app.get("/tasks/{task_id}", response_model=TaskResponse)
async def get_task(task_id: int, db: Session = Depends(get_db)):
    task = db.query(AgentTask).filter(AgentTask.id == task_id).first()
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task

@app.put("/tasks/{task_id}", response_model=TaskResponse)
async def update_task(task_id: int, status: str, result: Optional[str] = None, db: Session = Depends(get_db)):
    task = db.query(AgentTask).filter(AgentTask.id == task_id).first()
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    task.status = status
    if result:
        task.result = result
    task.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(task)
    return task

# Conversation endpoints
@app.post("/conversations", response_model=ConversationResponse)
async def create_conversation(conversation: ConversationCreate, db: Session = Depends(get_db)):
    # Simple AI response (you can integrate with OpenAI, Anthropic, etc.)
    ai_response = f"AI Agent đã nhận được: {conversation.user_message}"
    
    db_conversation = AgentConversation(
        user_message=conversation.user_message,
        ai_response=ai_response,
        session_id=conversation.session_id
    )
    db.add(db_conversation)
    db.commit()
    db.refresh(db_conversation)
    return db_conversation

@app.get("/conversations", response_model=List[ConversationResponse])
async def get_conversations(session_id: Optional[str] = None, skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    query = db.query(AgentConversation)
    if session_id:
        query = query.filter(AgentConversation.session_id == session_id)
    conversations = query.offset(skip).limit(limit).all()
    return conversations

if __name__ == "__main__":
    # Lazy import to avoid linter complaints when uvicorn is not installed in the active editor interpreter
    uvicorn = importlib.import_module("uvicorn")
    uvicorn.run(app, host="0.0.0.0", port=8000)