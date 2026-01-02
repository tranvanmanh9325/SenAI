"""
Embedding Pre-compute Service
Quản lý pre-computation của embeddings cho common queries
Tách riêng từ embedding_service.py để dễ bảo trì
"""
import os
import logging
import asyncio
from typing import List, Optional, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class EmbeddingPrecomputeManager:
    """Manager để quản lý pre-computation của embeddings"""
    
    def __init__(self, embedding_service):
        """
        Initialize precompute manager
        
        Args:
            embedding_service: Instance của EmbeddingService để generate embeddings
        """
        self.embedding_service = embedding_service
        
        # Pre-compute embeddings configuration
        self.precompute_enabled = os.getenv("EMBEDDING_PRECOMPUTE_ENABLED", "true").lower() == "true"
        self.precompute_common_queries = os.getenv("EMBEDDING_PRECOMPUTE_QUERIES", "true").lower() == "true"
        self._precompute_task = None
        self._common_queries = []  # List of common queries to pre-compute
        self._precomputed_embeddings = {}  # Cache for pre-computed embeddings
    
    def add_common_query(self, query: str, priority: int = 1):
        """
        Thêm common query vào danh sách để pre-compute
        
        Args:
            query: Query text
            priority: Độ ưu tiên (cao hơn = ưu tiên hơn)
        """
        if not query or not query.strip():
            return
        
        # Tránh duplicate
        for existing in self._common_queries:
            if existing["query"] == query:
                # Update priority nếu cao hơn
                if priority > existing["priority"]:
                    existing["priority"] = priority
                return
        
        self._common_queries.append({
            "query": query,
            "priority": priority,
            "added_at": datetime.now()
        })
        
        # Sort by priority (descending)
        self._common_queries.sort(key=lambda x: x["priority"], reverse=True)
        
        # Giới hạn số lượng common queries
        max_common_queries = int(os.getenv("EMBEDDING_MAX_COMMON_QUERIES", "100"))
        if len(self._common_queries) > max_common_queries:
            self._common_queries = self._common_queries[:max_common_queries]
        
        logger.debug(f"Added common query: {query[:50]}... (priority: {priority})")
    
    async def precompute_common_queries(self, limit: Optional[int] = None):
        """
        Pre-compute embeddings cho common queries
        
        Args:
            limit: Số lượng queries tối đa để pre-compute (None = all)
        """
        if not self.precompute_enabled or not self.precompute_common_queries:
            return
        
        if not self._common_queries:
            return
        
        queries_to_precompute = self._common_queries[:limit] if limit else self._common_queries
        
        if not queries_to_precompute:
            return
        
        logger.info(f"Pre-computing embeddings for {len(queries_to_precompute)} common queries...")
        
        # Extract query texts
        query_texts = [q["query"] for q in queries_to_precompute]
        
        # Generate embeddings in batch
        embeddings = await self.embedding_service.generate_embeddings_batch(
            texts=query_texts,
            use_cache=True,
            use_parallel=True
        )
        
        # Store pre-computed embeddings
        precomputed_count = 0
        for query_info, embedding in zip(queries_to_precompute, embeddings):
            if embedding:
                self._precomputed_embeddings[query_info["query"]] = {
                    "embedding": embedding,
                    "precomputed_at": datetime.now(),
                    "priority": query_info["priority"]
                }
                precomputed_count += 1
        
        logger.info(f"Pre-computed {precomputed_count}/{len(queries_to_precompute)} embeddings")
    
    def get_precomputed_embedding(self, query: str) -> Optional[List[float]]:
        """
        Lấy pre-computed embedding nếu có
        
        Args:
            query: Query text
            
        Returns:
            Embedding hoặc None
        """
        if query in self._precomputed_embeddings:
            return self._precomputed_embeddings[query]["embedding"]
        return None
    
    async def start_precompute_task(self, interval_seconds: int = 3600):
        """
        Bắt đầu background task để pre-compute embeddings định kỳ
        
        Args:
            interval_seconds: Khoảng thời gian giữa các lần pre-compute (default: 1 hour)
        """
        if not self.precompute_enabled:
            return
        
        async def precompute_loop():
            """Background loop để pre-compute"""
            while True:
                try:
                    await asyncio.sleep(interval_seconds)
                    await self.precompute_common_queries()
                except Exception as e:
                    logger.error(f"Error in precompute task: {e}")
                    await asyncio.sleep(60)  # Wait 1 minute before retry
        
        # Start background task
        if self._precompute_task is None or self._precompute_task.done():
            self._precompute_task = asyncio.create_task(precompute_loop())
            logger.info(f"Started precompute task (interval: {interval_seconds}s)")
    
    def stop_precompute_task(self):
        """Dừng background precompute task"""
        if self._precompute_task and not self._precompute_task.done():
            self._precompute_task.cancel()
            logger.info("Stopped precompute task")
    
    def get_precompute_stats(self) -> Dict[str, Any]:
        """Lấy thống kê về pre-compute"""
        return {
            "enabled": self.precompute_enabled,
            "common_queries_count": len(self._common_queries),
            "precomputed_count": len(self._precomputed_embeddings),
            "task_running": self._precompute_task is not None and not self._precompute_task.done() if self._precompute_task else False
        }