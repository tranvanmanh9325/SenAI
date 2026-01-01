"""
FastAPI application setup, middleware configuration, and route registration.
This module contains the main FastAPI app instance and all endpoint definitions.
"""
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import importlib
import logging

# Import configuration and models from app_config
from app_config import (
    SessionLocal,
    AsyncSessionLocal,
    lifespan,
    ALLOWED_ORIGINS,
    engine,
    async_engine,
    setup_database_indexes,
)

# Input validation & security helpers
from middleware.security import InputSizeLimitMiddleware

# Import rate limiting
from middleware.rate_limit import limiter_with_api_key, rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

# Import metrics
from middleware.metrics_middleware import MetricsMiddleware
from services.metrics_service import get_metrics_export

# Import LLM service
from services.llm_service import llm_service

# Re-export Pydantic models from app_config for backward compatibility
from app_config import (
    TaskCreate,
    TaskResponse,
    ConversationCreate,
    ConversationResponse,
    FeedbackCreate,
    FeedbackResponse,
    FeedbackStats,
)

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

# Dependency to get database session (sync - for backward compatibility)
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Dependency to get async database session
async def get_async_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

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
    from routes.database_optimization import router as db_optimization_router
    from routes.cache_routes import router as cache_router
    from routes.async_routes import async_router
    app.include_router(router)
    app.include_router(analysis_router)
    app.include_router(api_keys_router)
    app.include_router(db_optimization_router)
    app.include_router(cache_router)
    app.include_router(async_router)  # Async routes

_register_routes()

if __name__ == "__main__":
    import os
    
    # Lazy import to avoid linter complaints when uvicorn is not installed in the active editor interpreter
    uvicorn = importlib.import_module("uvicorn")
    
    # Note: Celery worker sẽ tự động start qua lifespan event nếu ENABLE_CELERY_WORKER=true
    # Nếu muốn start worker khi chạy python app.py, set ENABLE_CELERY_WORKER=true trong .env
    uvicorn.run(app, host="0.0.0.0", port=8000)