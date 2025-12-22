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
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    retry_if_exception
)

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
                response = await self._generate_ollama(
                    user_message, 
                    conversation_history, 
                    system_prompt,
                    temperature,
                    max_tokens
                )
            elif self.provider == "openai":
                response = await self._generate_openai(
                    user_message,
                    conversation_history,
                    system_prompt,
                    temperature,
                    max_tokens
                )
            elif self.provider == "anthropic":
                response = await self._generate_anthropic(
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
            logger.error(f"Connection error after retries: {e}")
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
            logger.error(f"HTTP error after retries: {e}")
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
            logger.error(f"Error generating response: {e}")
            return f"Xin lỗi, đã xảy ra lỗi khi tạo phản hồi: {str(e)}"
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.ConnectError, httpx.TimeoutException, httpx.HTTPStatusError)),
        reraise=True
    )
    async def _generate_ollama(
        self,
        user_message: str,
        conversation_history: Optional[List[Dict[str, str]]],
        system_prompt: Optional[str],
        temperature: float,
        max_tokens: Optional[int]
    ) -> str:
        """Generate response qua Ollama API với retry logic"""
        # Build messages
        messages = []
        
        # Add system prompt nếu có
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        # Add conversation history
        if conversation_history:
            messages.extend(conversation_history)
        
        # Add current user message
        messages.append({"role": "user", "content": user_message})
        
        # Thử với /api/generate trước (đơn giản hơn, ít lỗi hơn)
        # Nếu có system prompt hoặc history, sẽ thử /api/chat sau
        max_retries = 3
        for attempt in range(max_retries):
            try:
                # Luôn dùng /api/generate cho đơn giản và ổn định
                # Build prompt từ messages - format đơn giản cho Ollama
                url = f"{self.ollama_base_url}/api/generate"
                
                # Nếu chỉ có user message (không có system prompt và history), dùng trực tiếp
                if len(messages) == 1 and messages[0].get("role") == "user":
                    prompt = messages[0].get("content", user_message)
                    logger.debug(f"Simple prompt (user only): {prompt[:100]}...")
                else:
                    # Build prompt từ messages - format đơn giản
                    # Ollama hoạt động tốt với format: System prompt + User message
                    prompt_parts = []
                    for msg in messages:
                        role = msg.get("role", "user")
                        content = msg.get("content", "")
                        if role == "system":
                            # System prompt ở đầu, không cần prefix
                            prompt_parts.insert(0, content)
                        elif role == "user":
                            # User message
                            if prompt_parts:
                                prompt_parts.append(f"\n\nUser: {content}")
                            else:
                                prompt_parts.append(content)
                        elif role == "assistant":
                            # Assistant response trong history
                            prompt_parts.append(f"\n\nAssistant: {content}")
                    prompt = "\n".join(prompt_parts)
                    logger.debug(f"Built prompt from messages (length: {len(prompt)}): {prompt[:200]}...")
                
                # Tạo payload cho /api/generate
                payload = {
                    "model": self.model_name,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": temperature,
                    }
                }
                if max_tokens:
                    payload["options"]["num_predict"] = max_tokens
            
                logger.debug(f"Payload prepared: model={self.model_name}, prompt_length={len(prompt)}")
                
                logger.debug(f"Attempt {attempt + 1}: Sending request to Ollama: {url}, model: {self.model_name}")
                
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(url, json=payload)
                    response.raise_for_status()
                    data = response.json()
                    logger.info(f"Ollama response received. Keys: {list(data.keys())}, done_reason: {data.get('done_reason')}, done: {data.get('done')}")
                    
                    # Kiểm tra nếu model đang load
                    if data.get("done_reason") == "load":
                        if attempt < max_retries - 1:
                            logger.info(f"Model is loading, waiting and retrying... (attempt {attempt + 1}/{max_retries})")
                            import asyncio
                            await asyncio.sleep(2)  # Đợi 2 giây
                            continue
                        else:
                            logger.warning("Model still loading after retries")
                            return "Model đang được tải, vui lòng đợi vài giây rồi thử lại."
                    
                    # Extract response từ /api/generate format (ưu tiên)
                    if "response" in data:
                        result = data["response"]
                        logger.info(f"Found 'response' field. Type: {type(result)}, Value length: {len(str(result)) if result else 0}")
                        if result is not None:
                            result_str = str(result).strip()
                            if result_str:
                                logger.info(f"✅ Successfully extracted response from Ollama (length: {len(result_str)})")
                                return result_str
                            else:
                                logger.warning(f"Response field exists but is empty string. Full data: {data}")
                                # Nếu response rỗng nhưng done_reason là 'stop', có thể là model không generate gì
                                if data.get("done_reason") == "stop" and data.get("done"):
                                    logger.warning("Model returned empty response but marked as done")
                                    if attempt < max_retries - 1:
                                        logger.info(f"Retrying... (attempt {attempt + 1}/{max_retries})")
                                        import asyncio
                                        await asyncio.sleep(1)
                                        continue
                    
                    # Extract response từ /api/chat format (fallback)
                    if "message" in data:
                        message = data["message"]
                        logger.info(f"Found 'message' field. Type: {type(message)}")
                        if isinstance(message, dict) and "content" in message:
                            result = message["content"]
                            if result and result.strip():
                                logger.info(f"✅ Successfully extracted response from Ollama chat (length: {len(result)})")
                                return result
                        elif isinstance(message, str):
                            if message.strip():
                                logger.info(f"✅ Successfully extracted response from Ollama chat (string, length: {len(message)})")
                                return message
                    
                    # Nếu không tìm thấy response ở cả 2 format
                    logger.error(f"❌ Could not extract response from Ollama. Response keys: {list(data.keys())}")
                    logger.error(f"Response data: {data}")
                    if attempt < max_retries - 1:
                        logger.warning(f"Empty response, retrying... (attempt {attempt + 1}/{max_retries})")
                        import asyncio
                        await asyncio.sleep(1)
                        continue
                    else:
                        logger.error(f"Empty response after all retries: {data}")
                        return "Xin lỗi, không thể tạo phản hồi từ AI. Vui lòng thử lại."
                    
            except httpx.HTTPStatusError as e:
                logger.error(f"HTTP error from Ollama: {e}, status: {e.response.status_code}")
                if e.response.status_code == 404 and attempt == 0:
                    # Nếu /api/chat không tồn tại, thử /api/generate
                    logger.info("Ollama /api/chat not available, trying /api/generate")
                    continue
                if attempt < max_retries - 1:
                    logger.warning(f"HTTP error, retrying... (attempt {attempt + 1}/{max_retries}): {e}")
                    import asyncio
                    await asyncio.sleep(1)
                    continue
                raise
            except Exception as e:
                logger.error(f"Unexpected error in _generate_ollama: {e}", exc_info=True)
                if attempt < max_retries - 1:
                    logger.warning(f"Error, retrying... (attempt {attempt + 1}/{max_retries})")
                    import asyncio
                    await asyncio.sleep(1)
                    continue
                raise
        
        # Nếu tất cả retries đều fail
        return "Xin lỗi, không thể tạo phản hồi từ AI sau nhiều lần thử. Vui lòng kiểm tra Ollama đã chạy và model đã được tải chưa."
    
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.ConnectError, httpx.TimeoutException, httpx.HTTPStatusError)),
        reraise=True
    )
    async def _generate_openai(
        self,
        user_message: str,
        conversation_history: Optional[List[Dict[str, str]]],
        system_prompt: Optional[str],
        temperature: float,
        max_tokens: Optional[int]
    ) -> str:
        """Generate response qua OpenAI API với retry logic"""
        if not self.openai_api_key:
            raise ValueError("OPENAI_API_KEY not set")
        
        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.openai_api_key}",
            "Content-Type": "application/json"
        }
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        if conversation_history:
            messages.extend(conversation_history)
        messages.append({"role": "user", "content": user_message})
        
        payload = {
            "model": "gpt-3.5-turbo",
            "messages": messages,
            "temperature": temperature
        }
        if max_tokens:
            payload["max_tokens"] = max_tokens
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.ConnectError, httpx.TimeoutException, httpx.HTTPStatusError)),
        reraise=True
    )
    async def _generate_anthropic(
        self,
        user_message: str,
        conversation_history: Optional[List[Dict[str, str]]],
        system_prompt: Optional[str],
        temperature: float,
        max_tokens: Optional[int]
    ) -> str:
        """Generate response qua Anthropic API với retry logic"""
        if not self.anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY not set")
        
        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": self.anthropic_api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json"
        }
        
        messages = []
        if conversation_history:
            messages.extend(conversation_history)
        messages.append({"role": "user", "content": user_message})
        
        payload = {
            "model": "claude-3-sonnet-20240229",
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens or 1024
        }
        if system_prompt:
            payload["system"] = system_prompt
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            return data["content"][0]["text"]
    
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
        try:
            url = f"{self.ollama_base_url}/api/tags"
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(url)
                response.raise_for_status()
                data = response.json()
                models = [model.get("name", "") for model in data.get("models", [])]
                
                # Kiểm tra model có sẵn (hỗ trợ cả "llama3.1" và "llama3.1:latest")
                model_available = (
                    self.model_name in models or 
                    f"{self.model_name}:latest" in models or
                    any(model.startswith(self.model_name + ":") for model in models)
                )
                
                # Tìm model name chính xác nếu có
                exact_model = None
                if self.model_name in models:
                    exact_model = self.model_name
                elif f"{self.model_name}:latest" in models:
                    exact_model = f"{self.model_name}:latest"
                else:
                    # Tìm model bắt đầu bằng tên model
                    for model in models:
                        if model.startswith(self.model_name + ":"):
                            exact_model = model
                            break
                
                return {
                    "connected": True,
                    "models": models,
                    "current_model": self.model_name,
                    "exact_model": exact_model,
                    "model_available": model_available
                }
        except Exception as e:
            return {
                "connected": False,
                "error": str(e)
            }
    
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