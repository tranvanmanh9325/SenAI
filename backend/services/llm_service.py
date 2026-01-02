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
    
    def __init__(
        self,
        ollama_base_url: Optional[str] = None,
        model_name: Optional[str] = None,
        base_timeout: Optional[float] = None,
        openai_api_key: Optional[str] = None,
        anthropic_api_key: Optional[str] = None,
        provider: Optional[str] = None,
        min_timeout: Optional[float] = None,
        max_timeout: Optional[float] = None
    ):
        """
        Initialize LLMService with configuration.
        If parameters are not provided, they will be loaded from environment variables.
        
        Args:
            ollama_base_url: Ollama base URL (default: from env or "http://localhost:11434")
            model_name: Model name (default: from env or "llama3.1:latest")
            base_timeout: Base timeout in seconds (default: from env or 60.0)
            openai_api_key: OpenAI API key (default: from env)
            anthropic_api_key: Anthropic API key (default: from env)
            provider: Provider type ("ollama", "openai", "anthropic") (default: from env or "ollama")
            min_timeout: Minimum timeout in seconds (default: from env or 30.0)
            max_timeout: Maximum timeout in seconds (default: from env or 300.0)
        """
        # Ollama configuration (default cho llama3.1 local)
        self.ollama_base_url = ollama_base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        # Default model name với :latest suffix (Ollama format)
        self.model_name = model_name or os.getenv("LLM_MODEL_NAME", "llama3.1:latest")
        self.base_timeout = float(base_timeout or os.getenv("LLM_TIMEOUT", "60.0"))
        self.timeout = self.base_timeout  # Will be adapted per request
        
        # Alternative: OpenAI/Anthropic API (nếu cần)
        self.openai_api_key = openai_api_key or os.getenv("OPENAI_API_KEY")
        self.anthropic_api_key = anthropic_api_key or os.getenv("ANTHROPIC_API_KEY")
        
        # LLM provider preference
        self.provider = provider or os.getenv("LLM_PROVIDER", "ollama")  # ollama, openai, anthropic
        
        # Adaptive timeout configuration
        self.min_timeout = float(min_timeout or os.getenv("LLM_MIN_TIMEOUT", "30.0"))
        self.max_timeout = float(max_timeout or os.getenv("LLM_MAX_TIMEOUT", "300.0"))
        
        # Initialize provider instances (timeout will be set per request)
        self.ollama_provider = OllamaProvider(self.ollama_base_url, self.model_name, self.base_timeout)
        if self.openai_api_key:
            self.openai_provider = OpenAIProvider(self.openai_api_key, self.base_timeout)
        else:
            self.openai_provider = None
        if self.anthropic_api_key:
            self.anthropic_provider = AnthropicProvider(self.anthropic_api_key, self.base_timeout)
        else:
            self.anthropic_provider = None
    
    def _calculate_adaptive_timeout(
        self,
        user_message: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        system_prompt: Optional[str] = None,
        max_tokens: Optional[int] = None
    ) -> float:
        """
        Calculate adaptive timeout based on request complexity
        
        Factors:
        - Message length (longer = more time)
        - Conversation history length (more history = more time)
        - System prompt length
        - Max tokens requested
        """
        # Base timeout
        timeout = self.base_timeout
        
        # Estimate input tokens (rough: 1 token ≈ 4 characters)
        input_length = len(user_message)
        if system_prompt:
            input_length += len(system_prompt)
        if conversation_history:
            for msg in conversation_history:
                input_length += len(str(msg.get("content", "")))
        
        estimated_input_tokens = input_length / 4
        
        # Calculate timeout multiplier based on input size
        # Base: 30s for small requests (< 500 tokens)
        # Scale up: +1s per 100 tokens, up to max
        if estimated_input_tokens > 500:
            additional_time = (estimated_input_tokens - 500) / 100 * 1.0  # +1s per 100 tokens
            timeout = self.base_timeout + additional_time
        
        # Factor in max_tokens if specified
        if max_tokens:
            # More tokens requested = more time needed for generation
            timeout += max_tokens / 1000 * 5.0  # +5s per 1000 tokens
        
        # Factor in conversation history length
        if conversation_history:
            history_multiplier = 1 + (len(conversation_history) / 20) * 0.5  # Up to 1.5x for long history
            timeout *= history_multiplier
        
        # Clamp to min/max
        timeout = max(self.min_timeout, min(self.max_timeout, timeout))
        
        logger.debug(f"Adaptive timeout calculated: {timeout:.1f}s (input_tokens: ~{estimated_input_tokens:.0f}, max_tokens: {max_tokens})")
        
        return timeout
        
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
        
        # Calculate adaptive timeout for this request
        adaptive_timeout = self._calculate_adaptive_timeout(
            user_message, conversation_history, system_prompt, max_tokens
        )
        
        # Update provider timeout temporarily
        old_timeout = self.ollama_provider.timeout
        self.ollama_provider.timeout = adaptive_timeout
        if self.openai_provider:
            self.openai_provider.timeout = adaptive_timeout
        if self.anthropic_provider:
            self.anthropic_provider.timeout = adaptive_timeout
        
        try:
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
        finally:
            # Restore original timeout
            self.ollama_provider.timeout = old_timeout
            if self.openai_provider:
                self.openai_provider.timeout = old_timeout
            if self.anthropic_provider:
                self.anthropic_provider.timeout = old_timeout
    
    async def generate_stream(
        self,
        user_message: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None
    ):
        """
        Generate streaming AI response từ user message (Server-Sent Events)
        
        Args:
            user_message: Tin nhắn từ user
            conversation_history: Lịch sử hội thoại
            system_prompt: System prompt tùy chỉnh
            temperature: Độ sáng tạo (0.0-1.0)
            max_tokens: Số token tối đa
            
        Yields:
            Response chunks (strings)
        """
        # Calculate adaptive timeout for this request
        adaptive_timeout = self._calculate_adaptive_timeout(
            user_message, conversation_history, system_prompt, max_tokens
        )
        
        # Update provider timeout temporarily
        old_timeout = self.ollama_provider.timeout
        self.ollama_provider.timeout = adaptive_timeout
        if self.openai_provider:
            self.openai_provider.timeout = adaptive_timeout
        if self.anthropic_provider:
            self.anthropic_provider.timeout = adaptive_timeout
        
        try:
            if self.provider == "ollama":
                async for chunk in self.ollama_provider.generate_stream(
                    user_message,
                    conversation_history,
                    system_prompt,
                    temperature,
                    max_tokens
                ):
                    yield chunk
            elif self.provider == "openai":
                if not self.openai_provider:
                    yield f"[Error: OpenAI provider not initialized. Set OPENAI_API_KEY.]"
                    return
                async for chunk in self.openai_provider.generate_stream(
                    user_message,
                    conversation_history,
                    system_prompt,
                    temperature,
                    max_tokens
                ):
                    yield chunk
            elif self.provider == "anthropic":
                if not self.anthropic_provider:
                    yield f"[Error: Anthropic provider not initialized. Set ANTHROPIC_API_KEY.]"
                    return
                async for chunk in self.anthropic_provider.generate_stream(
                    user_message,
                    conversation_history,
                    system_prompt,
                    temperature,
                    max_tokens
                ):
                    yield chunk
            else:
                yield f"[Error: Unknown LLM provider: {self.provider}]"
        finally:
            # Restore original timeout
            self.ollama_provider.timeout = old_timeout
            if self.openai_provider:
                self.openai_provider.timeout = old_timeout
            if self.anthropic_provider:
                self.anthropic_provider.timeout = old_timeout
    
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
    
    async def generate_batch(
        self,
        requests: List[Dict[str, Any]],
        use_cache: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Generate batch LLM responses
        
        Args:
            requests: List of request dicts, each containing:
                - user_message: str
                - conversation_history: Optional[List[Dict[str, str]]]
                - system_prompt: Optional[str]
                - temperature: float (default: 0.7)
                - max_tokens: Optional[int]
            use_cache: Có sử dụng cache không (default: True)
        
        Returns:
            List of response dicts với keys: response, error, request_index
        """
        import asyncio
        
        async def process_request(index: int, req: Dict[str, Any]) -> Dict[str, Any]:
            """Process single request"""
            try:
                response = await self.generate_response(
                    user_message=req.get("user_message", ""),
                    conversation_history=req.get("conversation_history"),
                    system_prompt=req.get("system_prompt"),
                    temperature=req.get("temperature", 0.7),
                    max_tokens=req.get("max_tokens"),
                    use_cache=use_cache
                )
                return {
                    "request_index": index,
                    "response": response,
                    "error": None
                }
            except Exception as e:
                logger.error(f"Error processing batch request {index}: {e}")
                return {
                    "request_index": index,
                    "response": None,
                    "error": str(e)
                }
        
        # Process all requests concurrently (with reasonable limit)
        # Limit concurrent requests to avoid overwhelming the LLM service
        max_concurrent = int(os.getenv("LLM_BATCH_MAX_CONCURRENT", "10"))
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def process_with_limit(index: int, req: Dict[str, Any]):
            async with semaphore:
                return await process_request(index, req)
        
        # Create tasks for all requests
        tasks = [process_with_limit(i, req) for i, req in enumerate(requests)]
        
        # Execute all tasks concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results and handle exceptions
        final_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                final_results.append({
                    "request_index": i,
                    "response": None,
                    "error": str(result)
                })
            else:
                final_results.append(result)
        
        # Sort by request_index to maintain order
        final_results.sort(key=lambda x: x["request_index"])
        
        return final_results


# Global instance (for backward compatibility)
# New code should use dependency injection via factories.llm_factory.create_llm_service()
# or dependencies.get_llm_service()
from factories.llm_factory import create_llm_service
llm_service = create_llm_service()