"""
Embedding Service để generate và quản lý embeddings
Hỗ trợ cả Ollama embeddings và sentence-transformers
Có tích hợp Redis caching để tăng hiệu năng

Cải thiện:
- Batch embedding generation: xử lý nhiều texts cùng lúc
- Parallel embedding generation: xử lý song song với asyncio
- Model quantization: tối ưu model để giảm memory và tăng tốc độ
- Pre-compute embeddings: tính toán trước embeddings cho common queries
"""
import os
import logging
import asyncio
import time
from typing import List, Optional, Dict, Any
import numpy as np
from dotenv import load_dotenv
import httpx

load_dotenv()

logger = logging.getLogger(__name__)

# Import cache service nếu có
try:
    from .cache_service import cache_service
    CACHE_AVAILABLE = True
except ImportError:
    CACHE_AVAILABLE = False
    cache_service = None
    logger.warning("Cache service not available. Install redis package for caching support.")

# Import metrics service nếu có
try:
    from .metrics_service import metrics_service
    METRICS_AVAILABLE = True
except ImportError:
    METRICS_AVAILABLE = False
    metrics_service = None
    logger.warning("Metrics service not available.")

# Import precompute manager và model loader
from .embedding_precompute import EmbeddingPrecomputeManager
from .embedding_model_loader import EmbeddingModelLoader

class EmbeddingService:
    """Service để generate embeddings cho text với batch, parallel, và quantization support"""
    
    def __init__(self):
        # Configuration
        self.embedding_provider = os.getenv("EMBEDDING_PROVIDER", "sentence-transformers")  # sentence-transformers, ollama
        self.ollama_base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        self.ollama_embedding_model = os.getenv("OLLAMA_EMBEDDING_MODEL", "llama3.1")
        
        # Sentence transformers model (lightweight, multilingual)
        self.sentence_model_name = os.getenv("SENTENCE_MODEL", "paraphrase-multilingual-MiniLM-L12-v2")
        
        # Model quantization configuration
        self.use_quantization = os.getenv("EMBEDDING_USE_QUANTIZATION", "false").lower() == "true"
        self.quantization_method = os.getenv("EMBEDDING_QUANTIZATION_METHOD", "int8")  # int8, int4, float16
        
        # Model loader (tách riêng để dễ bảo trì)
        self.model_loader = EmbeddingModelLoader(
            sentence_model_name=self.sentence_model_name,
            use_quantization=self.use_quantization,
            quantization_method=self.quantization_method
        )
        
        # Batch processing configuration
        self.batch_size = int(os.getenv("EMBEDDING_BATCH_SIZE", "32"))  # Batch size cho sentence-transformers
        self.max_batch_size_ollama = int(os.getenv("OLLAMA_BATCH_SIZE", "10"))  # Ollama thường nhỏ hơn
        
        # Parallel processing configuration
        self.max_concurrent_requests = int(os.getenv("EMBEDDING_MAX_CONCURRENT", "10"))
        self._semaphore = None  # Will be initialized lazily
        
        # Pre-compute manager (tách riêng để dễ bảo trì)
        self.precompute_manager = EmbeddingPrecomputeManager(self)
    
    def _load_sentence_model(self):
        """Lazy load sentence-transformers model (delegate to model_loader)"""
        return self.model_loader.load_model()
    
    @property
    def _sentence_model(self):
        """Get sentence model from loader"""
        return self.model_loader.get_model()
    
    async def generate_embedding(
        self,
        text: str,
        text_type: str = "user_message",  # user_message, ai_response, combined
        use_cache: bool = True
    ) -> Optional[List[float]]:
        """
        Generate embedding cho text với caching support
        
        Args:
            text: Text cần generate embedding
            text_type: Loại text (để optimize nếu cần)
            use_cache: Có sử dụng cache không (default: True)
            
        Returns:
            List of floats (embedding vector) hoặc None nếu lỗi
        """
        if not text or not text.strip():
            return None
        
        import time
        start_time = time.time()
        
        # Try to get from cache first
        if use_cache and CACHE_AVAILABLE and cache_service and cache_service.enabled:
            cached_embedding = cache_service.get_cached_embedding(text)
            if cached_embedding:
                logger.debug(f"Cache hit for embedding: {text[:50]}...")
                if METRICS_AVAILABLE and metrics_service and metrics_service.enabled:
                    metrics_service.record_cache_hit("embedding")
                return cached_embedding
        
        if METRICS_AVAILABLE and metrics_service and metrics_service.enabled:
            metrics_service.record_cache_miss("embedding")
        
        try:
            # Generate embedding
            if self.embedding_provider == "ollama":
                embedding = await self._generate_ollama_embedding(text)
            else:
                embedding = self._generate_sentence_embedding(text)
            
            # Record metrics
            duration = time.time() - start_time
            if METRICS_AVAILABLE and metrics_service and metrics_service.enabled:
                metrics_service.record_embedding_request(
                    provider=self.embedding_provider,
                    status="success" if embedding else "error",
                    duration=duration
                )
            
            # Cache the result
            if embedding and use_cache and CACHE_AVAILABLE and cache_service and cache_service.enabled:
                cache_service.cache_embedding(text, embedding)
                logger.debug(f"Cached embedding: {text[:50]}...")
            
            return embedding
        except Exception as e:
            duration = time.time() - start_time
            if METRICS_AVAILABLE and metrics_service and metrics_service.enabled:
                metrics_service.record_embedding_request(
                    provider=self.embedding_provider,
                    status="error",
                    duration=duration
                )
                metrics_service.record_error(
                    error_type=type(e).__name__,
                    service="embedding"
                )
            logger.error(f"Error generating embedding: {e}")
            return None
    
    def _generate_sentence_embedding(self, text: str) -> Optional[List[float]]:
        """Generate embedding bằng sentence-transformers (single text)"""
        try:
            self._load_sentence_model()
            
            if not self._sentence_model:
                logger.error("Sentence-transformers model not available")
                return None
            
            # Generate embedding
            embedding = self._sentence_model.encode(text, convert_to_numpy=True)
            
            # Convert to list
            return embedding.tolist()
        except Exception as e:
            logger.error(f"Error generating sentence embedding: {e}")
            return None
    
    def _generate_sentence_embeddings_batch(self, texts: List[str]) -> List[Optional[List[float]]]:
        """Generate embeddings cho batch texts bằng sentence-transformers"""
        try:
            self._load_sentence_model()
            
            if not self._sentence_model:
                logger.error("Sentence-transformers model not available")
                return [None] * len(texts)
            
            # Filter empty texts
            non_empty_texts = []
            text_indices = []
            for i, text in enumerate(texts):
                if text and text.strip():
                    non_empty_texts.append(text)
                    text_indices.append(i)
            
            if not non_empty_texts:
                return [None] * len(texts)
            
            # Generate embeddings in batch (much faster than individual)
            embeddings = self._sentence_model.encode(
                non_empty_texts,
                batch_size=self.batch_size,
                convert_to_numpy=True,
                show_progress_bar=False
            )
            
            # Map results back to original indices
            results = [None] * len(texts)
            for idx, embedding in zip(text_indices, embeddings):
                results[idx] = embedding.tolist()
            
            return results
        except Exception as e:
            logger.error(f"Error generating sentence embeddings batch: {e}")
            return [None] * len(texts)
    
    async def _generate_ollama_embedding(self, text: str) -> Optional[List[float]]:
        """Generate embedding qua Ollama API (single text)"""
        try:
            url = f"{self.ollama_base_url}/api/embeddings"
            
            payload = {
                "model": self.ollama_embedding_model,
                "prompt": text
            }
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                data = response.json()
                
                if "embedding" in data:
                    return data["embedding"]
                else:
                    logger.error(f"Unexpected Ollama response format: {data}")
                    return None
        except httpx.ConnectError:
            logger.error(f"Cannot connect to Ollama at {self.ollama_base_url}")
            return None
        except Exception as e:
            logger.error(f"Error generating Ollama embedding: {e}")
            return None
    
    def _get_semaphore(self) -> asyncio.Semaphore:
        """Lazy initialization của semaphore"""
        if self._semaphore is None:
            self._semaphore = asyncio.Semaphore(self.max_concurrent_requests)
        return self._semaphore
    
    async def _generate_ollama_embeddings_batch(self, texts: List[str]) -> List[Optional[List[float]]]:
        """Generate embeddings cho batch texts qua Ollama API (parallel requests)"""
        async def generate_single(text: str) -> Optional[List[float]]:
            """Generate embedding cho một text"""
            semaphore = self._get_semaphore()
            async with semaphore:  # Limit concurrent requests
                return await self._generate_ollama_embedding(text)
        
        # Process all texts in parallel (with semaphore limit)
        tasks = [generate_single(text) for text in texts]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Handle exceptions
        final_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Error generating Ollama embedding for text {i}: {result}")
                final_results.append(None)
            else:
                final_results.append(result)
        
        return final_results
    
    async def generate_embeddings_batch(
        self,
        texts: List[str],
        text_type: str = "user_message",
        use_cache: bool = True,
        use_parallel: bool = True
    ) -> List[Optional[List[float]]]:
        """
        Generate embeddings cho batch texts với batch processing và parallel support
        
        Args:
            texts: List các texts cần generate embedding
            text_type: Loại text (để optimize nếu cần)
            use_cache: Có sử dụng cache không (default: True)
            use_parallel: Có sử dụng parallel processing không (default: True)
            
        Returns:
            List of embeddings (có thể có None nếu lỗi)
        """
        if not texts:
            return []
        
        import time
        start_time = time.time()
        
        # Filter empty texts
        valid_texts = []
        valid_indices = []
        for i, text in enumerate(texts):
            if text and text.strip():
                valid_texts.append(text)
                valid_indices.append(i)
        
        if not valid_texts:
            return [None] * len(texts)
        
        # Check cache first
        cached_results = {}
        texts_to_generate = []
        texts_to_generate_indices = []
        
        if use_cache and CACHE_AVAILABLE and cache_service and cache_service.enabled:
            for idx, text in zip(valid_indices, valid_texts):
                cached_embedding = cache_service.get_cached_embedding(text)
                if cached_embedding:
                    cached_results[idx] = cached_embedding
                    if METRICS_AVAILABLE and metrics_service and metrics_service.enabled:
                        metrics_service.record_cache_hit("embedding")
                else:
                    texts_to_generate.append(text)
                    texts_to_generate_indices.append(idx)
                    if METRICS_AVAILABLE and metrics_service and metrics_service.enabled:
                        metrics_service.record_cache_miss("embedding")
        else:
            texts_to_generate = valid_texts
            texts_to_generate_indices = valid_indices
        
        # Generate embeddings for texts not in cache
        generated_results = {}
        if texts_to_generate:
            try:
                if self.embedding_provider == "ollama":
                    # Ollama: parallel requests (không có native batch API)
                    if use_parallel:
                        generated_embeddings = await self._generate_ollama_embeddings_batch(texts_to_generate)
                    else:
                        # Sequential processing
                        generated_embeddings = []
                        for text in texts_to_generate:
                            emb = await self._generate_ollama_embedding(text)
                            generated_embeddings.append(emb)
                else:
                    # sentence-transformers: native batch processing
                    generated_embeddings = self._generate_sentence_embeddings_batch(texts_to_generate)
                
                # Map results to indices
                for i, (idx, embedding) in enumerate(zip(texts_to_generate_indices, generated_embeddings)):
                    generated_results[idx] = embedding
                    
                    # Cache the result
                    if embedding and use_cache and CACHE_AVAILABLE and cache_service and cache_service.enabled:
                        text = texts_to_generate[i]
                        cache_service.cache_embedding(text, embedding)
                
            except Exception as e:
                logger.error(f"Error generating batch embeddings: {e}")
                # Mark all as None
                for idx in texts_to_generate_indices:
                    generated_results[idx] = None
        
        # Combine cached and generated results
        all_results = [None] * len(texts)
        for idx in valid_indices:
            if idx in cached_results:
                all_results[idx] = cached_results[idx]
            elif idx in generated_results:
                all_results[idx] = generated_results[idx]
        
        # Record metrics
        duration = time.time() - start_time
        if METRICS_AVAILABLE and metrics_service and metrics_service.enabled:
            success_count = sum(1 for r in all_results if r is not None)
            metrics_service.record_embedding_request(
                provider=self.embedding_provider,
                status="success" if success_count > 0 else "error",
                duration=duration
            )
        
        logger.debug(f"Generated {len([r for r in all_results if r is not None])}/{len(texts)} embeddings in {duration:.2f}s")
        
        return all_results
    
    async def generate_embeddings_parallel(
        self,
        texts: List[str],
        text_type: str = "user_message",
        use_cache: bool = True,
        max_workers: Optional[int] = None
    ) -> List[Optional[List[float]]]:
        """
        Generate embeddings song song với asyncio (wrapper cho batch với parallel=True)
        
        Args:
            texts: List các texts cần generate embedding
            text_type: Loại text
            use_cache: Có sử dụng cache không
            max_workers: Số lượng workers tối đa (None = use default)
            
        Returns:
            List of embeddings
        """
        if max_workers:
            # Temporarily update semaphore
            old_semaphore = self._semaphore
            old_max = self.max_concurrent_requests
            self._semaphore = asyncio.Semaphore(max_workers)
            self.max_concurrent_requests = max_workers
        
        try:
            return await self.generate_embeddings_batch(
                texts=texts,
                text_type=text_type,
                use_cache=use_cache,
                use_parallel=True
            )
        finally:
            if max_workers:
                self._semaphore = old_semaphore
                self.max_concurrent_requests = old_max
    
    async def generate_conversation_embeddings(
        self,
        user_message: str,
        ai_response: Optional[str] = None,
        use_batch: bool = True
    ) -> Dict[str, Any]:
        """
        Generate embeddings cho cả conversation với batch support
        
        Args:
            user_message: User message
            ai_response: AI response (optional)
            use_batch: Sử dụng batch processing nếu có cả user và AI message
            
        Returns:
            Dict với các embeddings
        """
        result = {
            "user_message_embedding": None,
            "ai_response_embedding": None,
            "combined_embedding": None,
            "embedding_model": self.embedding_provider,
            "dimension": None
        }
        
        # Initialize variables
        user_emb = None
        ai_emb = None
        
        # Use batch processing nếu có cả user và AI message
        if use_batch and user_message and ai_response:
            texts_to_embed = [user_message, ai_response]
            embeddings = await self.generate_embeddings_batch(texts_to_embed, use_parallel=True)
            user_emb = embeddings[0]
            ai_emb = embeddings[1] if len(embeddings) > 1 else None
        else:
            # Generate individually
            if user_message:
                user_emb = await self.generate_embedding(user_message, "user_message")
            if ai_response:
                ai_emb = await self.generate_embedding(ai_response, "ai_response")
        
        result["user_message_embedding"] = user_emb
        result["ai_response_embedding"] = ai_emb
        
        if user_emb:
            result["dimension"] = len(user_emb)
        
        # Generate combined embedding (concatenate hoặc average)
        if user_emb and ai_emb:
            # Average của user và AI embeddings
            combined = np.array(user_emb) + np.array(ai_emb)
            combined = (combined / 2).tolist()
            result["combined_embedding"] = combined
        elif user_emb:
            result["combined_embedding"] = user_emb
        elif ai_emb:
            result["combined_embedding"] = ai_emb
        
        return result
    
    def get_embedding_dimension(self) -> int:
        """Lấy dimension của embedding model"""
        if self.embedding_provider == "ollama":
            # Ollama embeddings thường là 4096 hoặc 5120
            return 4096
        else:
            # sentence-transformers models
            if "MiniLM" in self.sentence_model_name:
                return 384
            elif "multilingual" in self.sentence_model_name.lower():
                return 384
            else:
                return 384  # Default
    
    async def check_embedding_service(self) -> Dict[str, Any]:
        """Kiểm tra embedding service có sẵn không"""
        try:
            if self.embedding_provider == "ollama":
                # Test Ollama connection
                url = f"{self.ollama_base_url}/api/tags"
                async with httpx.AsyncClient(timeout=5.0) as client:
                    response = await client.get(url)
                    response.raise_for_status()
                    return {
                        "available": True,
                        "provider": "ollama",
                        "model": self.ollama_embedding_model,
                        "base_url": self.ollama_base_url
                    }
            else:
                # Test sentence-transformers
                model = self._load_sentence_model()
                if model:
                    # Test encode
                    test_emb = model.encode("test", convert_to_numpy=True)
                    return {
                        "available": True,
                        "provider": "sentence-transformers",
                        "model": self.sentence_model_name,
                        "dimension": len(test_emb)
                    }
                else:
                    return {
                        "available": False,
                        "provider": "sentence-transformers",
                        "error": "Model not loaded"
                    }
        except Exception as e:
            return {
                "available": False,
                "error": str(e)
            }
    
    # Pre-compute methods - delegate to precompute_manager
    def add_common_query(self, query: str, priority: int = 1):
        """Thêm common query vào danh sách để pre-compute (delegate to precompute_manager)"""
        return self.precompute_manager.add_common_query(query, priority)
    
    async def precompute_common_queries(self, limit: Optional[int] = None):
        """Pre-compute embeddings cho common queries (delegate to precompute_manager)"""
        return await self.precompute_manager.precompute_common_queries(limit)
    
    def get_precomputed_embedding(self, query: str) -> Optional[List[float]]:
        """Lấy pre-computed embedding nếu có (delegate to precompute_manager)"""
        return self.precompute_manager.get_precomputed_embedding(query)
    
    async def start_precompute_task(self, interval_seconds: int = 3600):
        """Bắt đầu background task để pre-compute embeddings định kỳ (delegate to precompute_manager)"""
        return await self.precompute_manager.start_precompute_task(interval_seconds)
    
    def stop_precompute_task(self):
        """Dừng background precompute task (delegate to precompute_manager)"""
        return self.precompute_manager.stop_precompute_task()
    
    def get_precompute_stats(self) -> Dict[str, Any]:
        """Lấy thống kê về pre-compute (delegate to precompute_manager)"""
        return self.precompute_manager.get_precompute_stats()


# Global instance
embedding_service = EmbeddingService()