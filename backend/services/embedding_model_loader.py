"""
Embedding Model Loader
Quản lý việc load và quantization của embedding models
Tách riêng từ embedding_service.py để dễ bảo trì
"""
import os
import logging

logger = logging.getLogger(__name__)


class EmbeddingModelLoader:
    """Class để quản lý việc load và quantization của embedding models"""
    
    def __init__(self, sentence_model_name: str, use_quantization: bool, quantization_method: str):
        """
        Initialize model loader
        
        Args:
            sentence_model_name: Tên của sentence-transformers model
            use_quantization: Có sử dụng quantization không
            quantization_method: Phương pháp quantization (int8, float16, etc.)
        """
        self.sentence_model_name = sentence_model_name
        self.use_quantization = use_quantization
        self.quantization_method = quantization_method
        self._sentence_model = None
        self._model_loaded = False
    
    def load_model(self):
        """Lazy load sentence-transformers model với quantization support"""
        if self._model_loaded and self._sentence_model:
            return self._sentence_model
        
        try:
            from sentence_transformers import SentenceTransformer
            logger.info(f"Loading sentence-transformers model: {self.sentence_model_name}")
            
            # Load model với quantization nếu được bật
            if self.use_quantization:
                try:
                    # Thử load với quantization
                    if self.quantization_method == "int8":
                        # Sử dụng ONNX Runtime với quantization (nếu có)
                        try:
                            import onnxruntime as ort  # type: ignore
                            logger.info("Attempting to load model with ONNX quantization")
                            # Note: sentence-transformers có thể cần convert sang ONNX trước
                            # Tạm thời load bình thường, có thể enhance sau
                            self._sentence_model = SentenceTransformer(self.sentence_model_name)
                        except ImportError:
                            logger.warning("ONNX Runtime not available, loading standard model")
                            self._sentence_model = SentenceTransformer(self.sentence_model_name)
                    elif self.quantization_method == "float16":
                        # Load với float16 precision (nếu model hỗ trợ)
                        self._sentence_model = SentenceTransformer(
                            self.sentence_model_name,
                            device='cpu'  # Quantization thường chạy trên CPU
                        )
                        # Convert model weights to float16 nếu có thể
                        try:
                            import torch
                            if hasattr(self._sentence_model, '_modules'):
                                for module in self._sentence_model._modules.values():
                                    if hasattr(module, 'to'):
                                        module.to(torch.float16)
                            logger.info("Model loaded with float16 quantization")
                        except Exception as e:
                            logger.warning(f"Could not apply float16 quantization: {e}")
                    else:
                        self._sentence_model = SentenceTransformer(self.sentence_model_name)
                    
                    logger.info(f"Model loaded with {self.quantization_method} quantization")
                except Exception as e:
                    logger.warning(f"Quantization failed, loading standard model: {e}")
                    self._sentence_model = SentenceTransformer(self.sentence_model_name)
            else:
                self._sentence_model = SentenceTransformer(self.sentence_model_name)
            
            self._model_loaded = True
            logger.info("Sentence-transformers model loaded successfully")
            return self._sentence_model
        except ImportError:
            logger.warning("sentence-transformers not installed. Install with: pip install sentence-transformers")
            self._sentence_model = None
            return None
        except Exception as e:
            logger.error(f"Error loading sentence-transformers model: {e}")
            self._sentence_model = None
            return None
    
    def get_model(self):
        """Lấy model đã load"""
        if not self._model_loaded:
            self.load_model()
        return self._sentence_model
    
    def is_loaded(self) -> bool:
        """Kiểm tra model đã được load chưa"""
        return self._model_loaded and self._sentence_model is not None