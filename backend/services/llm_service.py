"""
LLM Service để tích hợp với llama3.1 qua Ollama API
Hỗ trợ cả local Ollama và các LLM API khác
"""
import os
import httpx
import logging
from typing import Optional, List, Dict, Any
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

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
        max_tokens: Optional[int] = None
    ) -> str:
        """
        Generate AI response từ user message
        
        Args:
            user_message: Tin nhắn từ user
            conversation_history: Lịch sử hội thoại (format: [{"role": "user", "content": "..."}, ...])
            system_prompt: System prompt tùy chỉnh
            temperature: Độ sáng tạo (0.0-1.0)
            max_tokens: Số token tối đa
            
        Returns:
            AI response string
        """
        try:
            if self.provider == "ollama":
                return await self._generate_ollama(
                    user_message, 
                    conversation_history, 
                    system_prompt,
                    temperature,
                    max_tokens
                )
            elif self.provider == "openai":
                return await self._generate_openai(
                    user_message,
                    conversation_history,
                    system_prompt,
                    temperature,
                    max_tokens
                )
            elif self.provider == "anthropic":
                return await self._generate_anthropic(
                    user_message,
                    conversation_history,
                    system_prompt,
                    temperature,
                    max_tokens
                )
            else:
                raise ValueError(f"Unknown LLM provider: {self.provider}")
        except Exception as e:
            logger.error(f"Error generating response: {e}")
            return f"Xin lỗi, đã xảy ra lỗi khi tạo phản hồi: {str(e)}"
    
    async def _generate_ollama(
        self,
        user_message: str,
        conversation_history: Optional[List[Dict[str, str]]],
        system_prompt: Optional[str],
        temperature: float,
        max_tokens: Optional[int]
    ) -> str:
        """Generate response qua Ollama API"""
        url = f"{self.ollama_base_url}/api/generate"
        
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
        
        # Prepare request
        payload = {
            "model": self.model_name,
            "prompt": user_message,  # Ollama có thể dùng prompt đơn giản
            "stream": False,
            "options": {
                "temperature": temperature,
            }
        }
        
        # Add max_tokens nếu có
        if max_tokens:
            payload["options"]["num_predict"] = max_tokens
        
        # Nếu có conversation history, dùng format messages (Ollama mới hơn)
        if conversation_history or system_prompt:
            payload = {
                "model": self.model_name,
                "messages": messages,
                "stream": False,
                "options": {
                    "temperature": temperature,
                }
            }
            if max_tokens:
                payload["options"]["num_predict"] = max_tokens
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                data = response.json()
                
                # Ollama response format
                if "response" in data:
                    return data["response"]
                elif "message" in data and "content" in data["message"]:
                    return data["message"]["content"]
                else:
                    return str(data)
            except httpx.ConnectError:
                logger.error(f"Cannot connect to Ollama at {self.ollama_base_url}")
                return "Không thể kết nối đến Ollama server. Vui lòng kiểm tra Ollama đã chạy chưa."
            except httpx.TimeoutException:
                logger.error("Ollama request timeout")
                return "Request timeout. Model có thể đang xử lý, vui lòng thử lại."
    
    async def _generate_openai(
        self,
        user_message: str,
        conversation_history: Optional[List[Dict[str, str]]],
        system_prompt: Optional[str],
        temperature: float,
        max_tokens: Optional[int]
    ) -> str:
        """Generate response qua OpenAI API"""
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
    
    async def _generate_anthropic(
        self,
        user_message: str,
        conversation_history: Optional[List[Dict[str, str]]],
        system_prompt: Optional[str],
        temperature: float,
        max_tokens: Optional[int]
    ) -> str:
        """Generate response qua Anthropic API"""
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