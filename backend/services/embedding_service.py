"""
Embedding Service để generate và quản lý embeddings
Hỗ trợ cả Ollama embeddings và sentence-transformers
Có tích hợp Redis caching để tăng hiệu năng
"""
import os
import json
import logging
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

class EmbeddingService:
    """Service để generate embeddings cho text"""
    
    def __init__(self):
        # Configuration
        self.embedding_provider = os.getenv("EMBEDDING_PROVIDER", "sentence-transformers")  # sentence-transformers, ollama
        self.ollama_base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        self.ollama_embedding_model = os.getenv("OLLAMA_EMBEDDING_MODEL", "llama3.1")
        
        # Sentence transformers model (lightweight, multilingual)
        self.sentence_model_name = os.getenv("SENTENCE_MODEL", "paraphrase-multilingual-MiniLM-L12-v2")
        self._sentence_model = None
        
        # Cache để tránh load model nhiều lần
        self._model_loaded = False
    
    def _load_sentence_model(self):
        """Lazy load sentence-transformers model"""
        if self._model_loaded and self._sentence_model:
            return
        
        try:
            from sentence_transformers import SentenceTransformer
            logger.info(f"Loading sentence-transformers model: {self.sentence_model_name}")
            self._sentence_model = SentenceTransformer(self.sentence_model_name)
            self._model_loaded = True
            logger.info("Sentence-transformers model loaded successfully")
        except ImportError:
            logger.warning("sentence-transformers not installed. Install with: pip install sentence-transformers")
            self._sentence_model = None
        except Exception as e:
            logger.error(f"Error loading sentence-transformers model: {e}")
            self._sentence_model = None
    
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
        """Generate embedding bằng sentence-transformers"""
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
    
    async def _generate_ollama_embedding(self, text: str) -> Optional[List[float]]:
        """Generate embedding qua Ollama API"""
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
    
    async def generate_conversation_embeddings(
        self,
        user_message: str,
        ai_response: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate embeddings cho cả conversation
        
        Args:
            user_message: User message
            ai_response: AI response (optional)
            
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
        
        # Generate user message embedding
        if user_message:
            user_emb = await self.generate_embedding(user_message, "user_message")
            result["user_message_embedding"] = user_emb
            if user_emb:
                result["dimension"] = len(user_emb)
        
        # Generate AI response embedding
        if ai_response:
            ai_emb = await self.generate_embedding(ai_response, "ai_response")
            result["ai_response_embedding"] = ai_emb
        
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
                self._load_sentence_model()
                if self._sentence_model:
                    # Test encode
                    test_emb = self._sentence_model.encode("test", convert_to_numpy=True)
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


# Global instance
embedding_service = EmbeddingService()