"""
Database Optimization Routes
Cung cấp endpoints để monitor và optimize database queries
"""
from fastapi import APIRouter, HTTPException, Depends, Request
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import Optional, Dict, Any
import logging

from middleware.auth import verify_api_key
from services.database_config import get_database_config
from services.query_optimizer import get_query_optimizer
from services.query_cache_service import get_query_cache_service
import app

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/api/db/pool/stats")
async def get_pool_stats(
    request: Request,
    api_key = Depends(verify_api_key)
):
    """Lấy thống kê về database connection pool"""
    try:
        db_config = get_database_config()
        pool_stats = db_config.get_pool_stats(app.engine)
        
        return {
            "pool_size": db_config.pool_size,
            "max_overflow": db_config.max_overflow,
            "current_stats": pool_stats,
            "read_replica_available": db_config.has_read_replica()
        }
    except Exception as e:
        logger.error(f"Error getting pool stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/db/query/explain")
async def explain_query(
    request: Request,
    query: str,
    params: Optional[Dict[str, Any]] = None,
    api_key = Depends(verify_api_key)
):
    """
    Chạy EXPLAIN ANALYZE cho một query
    
    Body:
        query: SQL query string
        params: Query parameters (optional)
    """
    try:
        optimizer = get_query_optimizer(app.engine)
        result = optimizer.explain_analyze(query, params)
        
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        
        return result
    except Exception as e:
        logger.error(f"Error explaining query: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/db/query/check-indexes")
async def check_index_usage(
    request: Request,
    query: str,
    params: Optional[Dict[str, Any]] = None,
    api_key = Depends(verify_api_key)
):
    """
    Kiểm tra xem query có sử dụng indexes không
    
    Body:
        query: SQL query string
        params: Query parameters (optional)
    """
    try:
        optimizer = get_query_optimizer(app.engine)
        result = optimizer.check_index_usage(query, params)
        
        return result
    except Exception as e:
        logger.error(f"Error checking index usage: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/db/query/slow")
async def get_slow_queries(
    request: Request,
    min_time: float = 100.0,
    api_key = Depends(verify_api_key)
):
    """
    Lấy danh sách slow queries từ pg_stat_statements
    
    Args:
        min_time: Minimum execution time in milliseconds (default: 100)
    """
    try:
        optimizer = get_query_optimizer(app.engine)
        slow_queries = optimizer.analyze_slow_queries(min_execution_time=min_time)
        
        return {
            "slow_queries": slow_queries,
            "count": len(slow_queries),
            "min_execution_time": min_time
        }
    except Exception as e:
        logger.error(f"Error getting slow queries: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/db/cache/stats")
async def get_cache_stats(
    request: Request,
    api_key = Depends(verify_api_key)
):
    """Lấy thống kê về query cache"""
    try:
        cache_service = get_query_cache_service()
        stats = cache_service.get_stats()
        
        return stats
    except Exception as e:
        logger.error(f"Error getting cache stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/db/cache/invalidate")
async def invalidate_cache(
    request: Request,
    pattern: Optional[str] = None,
    api_key = Depends(verify_api_key)
):
    """
    Invalidate cache entries
    
    Body:
        pattern: Pattern để match keys (optional, None = clear all)
    """
    try:
        cache_service = get_query_cache_service()
        count = cache_service.invalidate(pattern)
        
        return {
            "message": f"Invalidated {count} cache entries",
            "count": count,
            "pattern": pattern
        }
    except Exception as e:
        logger.error(f"Error invalidating cache: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/db/health")
async def database_health(
    request: Request,
    db: Session = Depends(app.get_db)
):
    """
    Kiểm tra health của database và connection pool
    Public endpoint - không yêu cầu API key (dùng cho monitoring)
    """
    try:
        # Test database connection
        db.execute(text("SELECT 1"))
        
        # Get pool stats
        db_config = get_database_config()
        pool_stats = db_config.get_pool_stats(app.engine)
        
        # Get cache stats
        cache_service = get_query_cache_service()
        cache_stats = cache_service.get_stats()
        
        return {
            "status": "healthy",
            "database": "connected",
            "pool": {
                "size": pool_stats["size"],
                "checked_in": pool_stats["checked_in"],
                "checked_out": pool_stats["checked_out"],
                "overflow": pool_stats["overflow"]
            },
            "cache": {
                "backend": cache_stats["backend"],
                "hit_rate": cache_stats["hit_rate"],
                "hits": cache_stats["hits"],
                "misses": cache_stats["misses"]
            },
            "read_replica": {
                "available": db_config.has_read_replica(),
                "host": db_config.read_replica_host if db_config.has_read_replica() else None
            }
        }
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        raise HTTPException(status_code=503, detail=f"Database health check failed: {str(e)}")