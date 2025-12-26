"""
LLM Service để tích hợp với llama3.1 qua Ollama API
Hỗ trợ cả local Ollama và các LLM API khác
Có tích hợp Redis caching để tăng hiệu năng
"""
import os
import httpx
import logging
from typing import Optional, List, Dict, Any
from dotenv import load_dotenv

# Import centralized error handler
from .error_handler import log_error, ErrorCategory, ErrorSeverity

# Import provider implementations
from .llm_providers import OllamaProvider, OpenAIProvider, AnthropicProvider

load_dotenv()

logger = logging.getLogger(__name__)
# Đảm bảo logger ở level DEBUG để xem tất cả logs
logger.setLevel(logging.DEBUG)

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

class LLMService:
    """Service để tương tác với LLM (llama3.1 qua Ollama)"""
    
    def __init__(self):
        # Ollama configuration (default cho llama3.1 local)
        self.ollama_base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        # Default model name với :latest suffix (Ollama format)
        self.model_name = os.getenv("LLM_MODEL_NAME", "llama3.1:latest")
        self.timeout = float(os.getenv("LLM_TIMEOUT", "60.0"))
        
        # Alternative: OpenAI/Anthropic API (nếu cần)
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        self.anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
        
        # LLM provider preference
        self.provider = os.getenv("LLM_PROVIDER", "ollama")  # ollama, openai, anthropic
        
        # Initialize provider instances
        self.ollama_provider = OllamaProvider(self.ollama_base_url, self.model_name, self.timeout)
        if self.openai_api_key:
            self.openai_provider = OpenAIProvider(self.openai_api_key, self.timeout)
        else:
            self.openai_provider = None
        if self.anthropic_api_key:
            self.anthropic_provider = AnthropicProvider(self.anthropic_api_key, self.timeout)
        else:
            self.anthropic_provider = None
        
    async def generate_response(
        self, 
        user_message: str, 
        conversation_history: Optional[List[Dict[str, str]]] = None,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        use_cache: bool = True
    ) -> str:
        """
        Generate AI response từ user message với caching support
        
        Args:
            user_message: Tin nhắn từ user
            conversation_history: Lịch sử hội thoại (format: [{"role": "user", "content": "..."}, ...])
            system_prompt: System prompt tùy chỉnh
            temperature: Độ sáng tạo (0.0-1.0)
            max_tokens: Số token tối đa
            use_cache: Có sử dụng cache không (default: True)
            
        Returns:
            AI response string
        """
        import time
        start_time = time.time()
        
        # Try to get from cache first (only if no conversation history for simplicity)
        if use_cache and CACHE_AVAILABLE and cache_service and cache_service.enabled:
            # Only cache simple requests without conversation history
            if not conversation_history or len(conversation_history) == 0:
                cached_response = cache_service.get_cached_llm_response(
                    user_message, conversation_history, system_prompt, temperature
                )
                if cached_response:
                    # Kiểm tra xem cached response có phải là error message không
                    error_keywords = [
                        "Xin lỗi, không thể",
                        "Không thể kết nối",
                        "Lỗi từ",
                        "đã xảy ra lỗi",
                        "Model đang được tải"
                    ]
                    is_error = any(keyword in cached_response for keyword in error_keywords)
                    if not is_error:
                        logger.debug(f"Cache hit for LLM response: {user_message[:50]}...")
                        if METRICS_AVAILABLE and metrics_service and metrics_service.enabled:
                            metrics_service.record_cache_hit("llm")
                        return cached_response
                    else:
                        logger.debug(f"Cache hit but response is error message, ignoring cache: {cached_response[:50]}...")
                        # Xóa cache entry này vì nó là error
                        try:
                            cache_service.clear_llm_cache(user_message, conversation_history, system_prompt, temperature)
                        except:
                            pass
        
        if METRICS_AVAILABLE and metrics_service and metrics_service.enabled:
            metrics_service.record_cache_miss("llm")
        
        try:
            if self.provider == "ollama":
                response = await self.ollama_provider.generate(
                    user_message, 
                    conversation_history, 
                    system_prompt,
                    temperature,
                    max_tokens
                )
            elif self.provider == "openai":
                if not self.openai_provider:
                    raise ValueError("OpenAI provider not initialized. Set OPENAI_API_KEY.")
                response = await self.openai_provider.generate(
                    user_message,
                    conversation_history,
                    system_prompt,
                    temperature,
                    max_tokens
                )
            elif self.provider == "anthropic":
                if not self.anthropic_provider:
                    raise ValueError("Anthropic provider not initialized. Set ANTHROPIC_API_KEY.")
                response = await self.anthropic_provider.generate(
                    user_message,
                    conversation_history,
                    system_prompt,
                    temperature,
                    max_tokens
                )
            else:
                raise ValueError(f"Unknown LLM provider: {self.provider}")
            
            # Record metrics
            duration = time.time() - start_time
            if METRICS_AVAILABLE and metrics_service and metrics_service.enabled:
                # Estimate tokens (rough approximation: 1 token ≈ 4 characters)
                input_tokens = len(user_message) // 4
                if conversation_history:
                    input_tokens += sum(len(str(msg.get("content", ""))) for msg in conversation_history) // 4
                output_tokens = len(response) // 4 if response else 0
                
                metrics_service.record_llm_request(
                    provider=self.provider,
                    status="success",
                    duration=duration,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens
                )
            
            # Cache the response (only if no conversation history và không phải error message)
            if response and use_cache and CACHE_AVAILABLE and cache_service and cache_service.enabled:
                # Không cache error messages
                error_keywords = [
                    "Xin lỗi, không thể",
                    "Không thể kết nối",
                    "Lỗi từ",
                    "đã xảy ra lỗi",
                    "Model đang được tải"
                ]
                is_error = any(keyword in response for keyword in error_keywords)
                
                if not is_error and (not conversation_history or len(conversation_history) == 0):
                    cache_service.cache_llm_response(
                        user_message, response, conversation_history, system_prompt, temperature
                    )
                    logger.debug(f"Cached LLM response: {user_message[:50]}...")
                elif is_error:
                    logger.debug(f"Not caching error response: {response[:50]}...")
            
            return response
        except (httpx.ConnectError, httpx.TimeoutException) as e:
            duration = time.time() - start_time
            if METRICS_AVAILABLE and metrics_service and metrics_service.enabled:
                metrics_service.record_llm_request(
                    provider=self.provider,
                    status="connection_error",
                    duration=duration
                )
                metrics_service.record_error(
                    error_type=type(e).__name__,
                    service="llm"
                )
            # Use centralized error handler
            log_error(
                e,
                category=ErrorCategory.NETWORK,
                severity=ErrorSeverity.ERROR,
                context="LLMService.generate_response",
                include_stack_trace=True
            )
            if self.provider == "ollama":
                return "Không thể kết nối đến Ollama server sau nhiều lần thử. Vui lòng kiểm tra Ollama đã chạy chưa."
            else:
                return f"Không thể kết nối đến {self.provider} API. Vui lòng thử lại sau."
        except httpx.HTTPStatusError as e:
            duration = time.time() - start_time
            if METRICS_AVAILABLE and metrics_service and metrics_service.enabled:
                metrics_service.record_llm_request(
                    provider=self.provider,
                    status="http_error",
                    duration=duration
                )
                metrics_service.record_error(
                    error_type=type(e).__name__,
                    service="llm"
                )
            # Use centralized error handler
            log_error(
                e,
                category=ErrorCategory.EXTERNAL_API,
                severity=ErrorSeverity.ERROR,
                context="LLMService.generate_response",
                include_stack_trace=True
            )
            return f"Lỗi từ {self.provider} API: {e.response.status_code}. Vui lòng thử lại sau."
        except Exception as e:
            duration = time.time() - start_time
            if METRICS_AVAILABLE and metrics_service and metrics_service.enabled:
                metrics_service.record_llm_request(
                    provider=self.provider,
                    status="error",
                    duration=duration
                )
                metrics_service.record_error(
                    error_type=type(e).__name__,
                    service="llm"
                )
            # Use centralized error handler
            log_error(
                e,
                category=ErrorCategory.LLM,
                severity=ErrorSeverity.ERROR,
                context="LLMService.generate_response",
                include_stack_trace=True
            )
            return f"Xin lỗi, đã xảy ra lỗi khi tạo phản hồi: {str(e)}"
    
    async def _ensure_model_loaded(self) -> bool:
        """Đảm bảo model đã được load trong Ollama"""
        try:
            # Preload model bằng cách gửi một request nhỏ
            url = f"{self.ollama_base_url}/api/generate"
            payload = {
                "model": self.model_name,
                "prompt": "test",
                "stream": False,
                "options": {
                    "num_predict": 1  # Chỉ generate 1 token để load model
                }
            }
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                data = response.json()
                # Kiểm tra xem model đã load chưa
                if data.get("done_reason") != "load" or data.get("response"):
                    return True
            return False
        except Exception as e:
            logger.warning(f"Error preloading model: {e}")
            return False
    
    async def check_ollama_connection(self) -> Dict[str, Any]:
        """Kiểm tra kết nối đến Ollama"""
        return await self.ollama_provider.check_connection()
    
    def get_system_prompt(
        self, 
        use_fine_tuned: bool = False,
        pattern_insights: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Lấy system prompt, có thể tùy chỉnh từ fine-tuning và patterns
        
        Args:
            use_fine_tuned: Có sử dụng fine-tuned prompt không
            pattern_insights: Insights từ pattern analysis
        """
        base_prompt = """Bạn là một AI assistant thông minh và hữu ích. 
Hãy trả lời câu hỏi một cách chính xác, thân thiện và hữu ích.
Nếu bạn không biết câu trả lời, hãy thành thật nói rằng bạn không biết."""
        
        # Thêm pattern insights nếu có
        if pattern_insights:
            insights = pattern_insights.get("insights", [])
            if insights:
                base_prompt += "\n\nLưu ý từ phân tích patterns:\n"
                for insight in insights[:3]:  # Top 3 insights
                    base_prompt += f"- {insight}\n"
            
            # Thêm recommended approach
            recommended = pattern_insights.get("recommended_approach")
            if recommended and recommended.get("style") == "similar_to_high_rated":
                base_prompt += "\nHãy tham khảo phong cách từ các responses được đánh giá cao."
        
        # TODO: Load fine-tuned prompt từ database nếu có
        if use_fine_tuned:
            # Có thể load từ database hoặc file
            pass
        
        return base_prompt


# Global instance
llm_service = LLMService()