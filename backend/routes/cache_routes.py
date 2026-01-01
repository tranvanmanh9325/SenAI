"""
Cache Management Routes
Cung cấp endpoints để quản lý và monitor cache
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Dict, Any, Optional
import logging

# Import dependencies from app (same pattern as other routes)
import app

from services.cache_service import cache_service
from services.advanced_cache_service import get_advanced_cache_service

logger = logging.getLogger(__name__)

# Get get_db from app module
get_db = app.get_db

router = APIRouter(prefix="/cache", tags=["cache"])


@router.get("/stats")
async def get_cache_stats(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Lấy thống kê về cache performance
    """
    try:
        # Initialize advanced cache with db session if available
        advanced_cache = get_advanced_cache_service(db_session=db)
        stats = advanced_cache.get_stats()
        
        return {
            "status": "success",
            "stats": stats
        }
    except Exception as e:
        logger.error(f"Error getting cache stats: {e}")
        # Fallback to basic stats
        return {
            "status": "success",
            "stats": cache_service.get_stats()
        }


@router.post("/warm")
async def warm_cache(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Manually trigger cache warming
    """
    try:
        advanced_cache = get_advanced_cache_service(db_session=db)
        result = advanced_cache.warm_cache_now()
        
        return {
            "status": "success",
            "message": "Cache warming completed",
            **result
        }
    except Exception as e:
        logger.error(f"Error warming cache: {e}")
        raise HTTPException(status_code=500, detail=f"Cache warming failed: {str(e)}")


@router.delete("/clear")
async def clear_cache(
    pattern: Optional[str] = None,
    cache_type: Optional[str] = None,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Clear cache entries
    
    Args:
        pattern: Pattern to match keys (e.g., "embedding:*", "llm:*")
        cache_type: Type of cache to clear (embedding, llm, pattern_analysis)
    """
    try:
        advanced_cache = get_advanced_cache_service(db_session=db)
        
        if cache_type:
            # Clear by cache type
            pattern = f"{cache_type}:*" if not pattern else pattern
        
        if pattern:
            count = advanced_cache.invalidate_pattern(pattern)
        else:
            # Clear all (use with caution)
            count = advanced_cache.invalidate_pattern("*")
        
        return {
            "status": "success",
            "message": f"Cleared {count} cache entries",
            "pattern": pattern or "*",
            "count": count
        }
    except Exception as e:
        logger.error(f"Error clearing cache: {e}")
        raise HTTPException(status_code=500, detail=f"Cache clear failed: {str(e)}")


@router.get("/health")
async def cache_health(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Check cache health and availability
    """
    try:
        advanced_cache = get_advanced_cache_service(db_session=db)
        stats = advanced_cache.get_stats()
        
        health = {
            "status": "healthy",
            "l1": {
                "enabled": True,
                "size": stats.get("l1", {}).get("size", 0),
                "max_size": stats.get("l1", {}).get("max_size", 0)
            },
            "l2": {
                "enabled": stats.get("l2", {}).get("enabled", False)
            },
            "l3": {
                "enabled": stats.get("l3", {}).get("enabled", False)
            },
            "hit_rate": stats.get("hit_rate", 0.0)
        }
        
        # Check if any level is unhealthy
        if stats.get("l2", {}).get("enabled") is False and stats.get("l3", {}).get("enabled") is False:
            health["status"] = "degraded"
            health["message"] = "Only L1 cache available"
        
        return health
    except Exception as e:
        logger.error(f"Error checking cache health: {e}")
        return {
            "status": "unhealthy",
            "error": str(e)
        }