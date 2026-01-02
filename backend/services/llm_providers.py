"""
LLM Provider Implementations
Chứa các implementation cụ thể cho từng LLM provider (Ollama, OpenAI, Anthropic)
"""
import httpx
import logging
import asyncio
from typing import Optional, List, Dict, Any
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type
)

logger = logging.getLogger(__name__)


class OllamaProvider:
    """Provider implementation cho Ollama API"""
    
    def __init__(self, base_url: str, model_name: str, timeout: float):
        self.base_url = base_url
        self.model_name = model_name
        self.timeout = timeout
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.ConnectError, httpx.TimeoutException, httpx.HTTPStatusError)),
        reraise=True
    )
    async def generate(
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
                url = f"{self.base_url}/api/generate"
                
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
                    await asyncio.sleep(1)
                    continue
                raise
            except Exception as e:
                logger.error(f"Unexpected error in OllamaProvider.generate: {e}", exc_info=True)
                if attempt < max_retries - 1:
                    logger.warning(f"Error, retrying... (attempt {attempt + 1}/{max_retries})")
                    await asyncio.sleep(1)
                    continue
                raise
        
        # Nếu tất cả retries đều fail
        return "Xin lỗi, không thể tạo phản hồi từ AI sau nhiều lần thử. Vui lòng kiểm tra Ollama đã chạy và model đã được tải chưa."
    
    async def generate_stream(
        self,
        user_message: str,
        conversation_history: Optional[List[Dict[str, str]]],
        system_prompt: Optional[str],
        temperature: float,
        max_tokens: Optional[int]
    ):
        """Generate streaming response qua Ollama API"""
        import json
        
        # Build messages
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        if conversation_history:
            messages.extend(conversation_history)
        messages.append({"role": "user", "content": user_message})
        
        # Build prompt từ messages
        if len(messages) == 1 and messages[0].get("role") == "user":
            prompt = messages[0].get("content", user_message)
        else:
            prompt_parts = []
            for msg in messages:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                if role == "system":
                    prompt_parts.insert(0, content)
                elif role == "user":
                    if prompt_parts:
                        prompt_parts.append(f"\n\nUser: {content}")
                    else:
                        prompt_parts.append(content)
                elif role == "assistant":
                    prompt_parts.append(f"\n\nAssistant: {content}")
            prompt = "\n".join(prompt_parts)
        
        # Create payload with streaming enabled
        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "stream": True,
            "options": {
                "temperature": temperature,
            }
        }
        if max_tokens:
            payload["options"]["num_predict"] = max_tokens
        
        url = f"{self.base_url}/api/generate"
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                async with client.stream("POST", url, json=payload) as response:
                    response.raise_for_status()
                    full_response = ""
                    
                    async for line in response.aiter_lines():
                        if not line.strip():
                            continue
                        
                        try:
                            data = json.loads(line)
                            
                            # Extract response chunk
                            if "response" in data:
                                chunk = data["response"]
                                if chunk:
                                    full_response += chunk
                                    yield chunk
                            
                            # Check if done
                            if data.get("done", False):
                                break
                        except json.JSONDecodeError:
                            logger.warning(f"Failed to parse JSON line: {line}")
                            continue
                        
        except Exception as e:
            logger.error(f"Error in streaming: {e}")
            yield f"[Error: {str(e)}]"
    
    async def check_connection(self) -> Dict[str, Any]:
        """Kiểm tra kết nối đến Ollama"""
        try:
            url = f"{self.base_url}/api/tags"
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


class OpenAIProvider:
    """Provider implementation cho OpenAI API"""
    
    def __init__(self, api_key: str, timeout: float):
        self.api_key = api_key
        self.timeout = timeout
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.ConnectError, httpx.TimeoutException, httpx.HTTPStatusError)),
        reraise=True
    )
    async def generate(
        self,
        user_message: str,
        conversation_history: Optional[List[Dict[str, str]]],
        system_prompt: Optional[str],
        temperature: float,
        max_tokens: Optional[int]
    ) -> str:
        """Generate response qua OpenAI API với retry logic"""
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY not set")
        
        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
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
    
    async def generate_stream(
        self,
        user_message: str,
        conversation_history: Optional[List[Dict[str, str]]],
        system_prompt: Optional[str],
        temperature: float,
        max_tokens: Optional[int]
    ):
        """Generate streaming response qua OpenAI API"""
        import json
        
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY not set")
        
        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
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
            "temperature": temperature,
            "stream": True
        }
        if max_tokens:
            payload["max_tokens"] = max_tokens
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                async with client.stream("POST", url, headers=headers, json=payload) as response:
                    response.raise_for_status()
                    
                    async for line in response.aiter_lines():
                        if not line.strip() or not line.startswith("data: "):
                            continue
                        
                        data_str = line[6:]  # Remove "data: " prefix
                        if data_str == "[DONE]":
                            break
                        
                        try:
                            data = json.loads(data_str)
                            choices = data.get("choices", [])
                            if choices:
                                delta = choices[0].get("delta", {})
                                chunk = delta.get("content", "")
                                if chunk:
                                    yield chunk
                        except json.JSONDecodeError:
                            continue
        except Exception as e:
            logger.error(f"Error in OpenAI streaming: {e}")
            yield f"[Error: {str(e)}]"


class AnthropicProvider:
    """Provider implementation cho Anthropic API"""
    
    def __init__(self, api_key: str, timeout: float):
        self.api_key = api_key
        self.timeout = timeout
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.ConnectError, httpx.TimeoutException, httpx.HTTPStatusError)),
        reraise=True
    )
    async def generate(
        self,
        user_message: str,
        conversation_history: Optional[List[Dict[str, str]]],
        system_prompt: Optional[str],
        temperature: float,
        max_tokens: Optional[int]
    ) -> str:
        """Generate response qua Anthropic API với retry logic"""
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY not set")
        
        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": self.api_key,
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
    
    async def generate_stream(
        self,
        user_message: str,
        conversation_history: Optional[List[Dict[str, str]]],
        system_prompt: Optional[str],
        temperature: float,
        max_tokens: Optional[int]
    ):
        """Generate streaming response qua Anthropic API"""
        import json
        
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY not set")
        
        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": self.api_key,
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
            "max_tokens": max_tokens or 1024,
            "stream": True
        }
        if system_prompt:
            payload["system"] = system_prompt
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                async with client.stream("POST", url, headers=headers, json=payload) as response:
                    response.raise_for_status()
                    
                    async for line in response.aiter_lines():
                        if not line.strip():
                            continue
                        
                        try:
                            # Anthropic uses event-stream format
                            if line.startswith("data: "):
                                data_str = line[6:]
                                if data_str == "[DONE]":
                                    break
                                data = json.loads(data_str)
                                
                                if data.get("type") == "content_block_delta":
                                    delta = data.get("delta", {})
                                    chunk = delta.get("text", "")
                                    if chunk:
                                        yield chunk
                        except json.JSONDecodeError:
                            continue
        except Exception as e:
            logger.error(f"Error in Anthropic streaming: {e}")
            yield f"[Error: {str(e)}]"