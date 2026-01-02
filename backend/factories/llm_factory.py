"""
Factory for creating LLM service and providers.
Implements Factory pattern to create LLM providers based on configuration.
"""
import os
import logging
from typing import Optional
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

load_dotenv()


class LLMProviderFactory:
    """Factory class for creating LLM provider instances"""
    
    @staticmethod
    def create_ollama_provider(base_url: str, model_name: str, timeout: float):
        """Create Ollama provider instance"""
        from services.llm_providers import OllamaProvider
        return OllamaProvider(base_url, model_name, timeout)
    
    @staticmethod
    def create_openai_provider(api_key: str, timeout: float):
        """Create OpenAI provider instance"""
        from services.llm_providers import OpenAIProvider
        return OpenAIProvider(api_key, timeout)
    
    @staticmethod
    def create_anthropic_provider(api_key: str, timeout: float):
        """Create Anthropic provider instance"""
        from services.llm_providers import AnthropicProvider
        return AnthropicProvider(api_key, timeout)
    
    @classmethod
    def create_provider(cls, provider_type: str, **kwargs):
        """
        Create provider instance based on provider type
        
        Args:
            provider_type: Type of provider ('ollama', 'openai', 'anthropic')
            **kwargs: Provider-specific arguments
        
        Returns:
            Provider instance
        """
        if provider_type == "ollama":
            return cls.create_ollama_provider(
                kwargs.get("base_url"),
                kwargs.get("model_name"),
                kwargs.get("timeout")
            )
        elif provider_type == "openai":
            return cls.create_openai_provider(
                kwargs.get("api_key"),
                kwargs.get("timeout")
            )
        elif provider_type == "anthropic":
            return cls.create_anthropic_provider(
                kwargs.get("api_key"),
                kwargs.get("timeout")
            )
        else:
            raise ValueError(f"Unknown LLM provider type: {provider_type}")


def create_llm_service():
    """
    Factory function to create LLMService instance.
    This function creates and configures an LLMService with appropriate providers.
    
    Returns:
        LLMService instance
    """
    from services.llm_service import LLMService
    
    # Get configuration from environment
    ollama_base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    model_name = os.getenv("LLM_MODEL_NAME", "llama3.1:latest")
    base_timeout = float(os.getenv("LLM_TIMEOUT", "60.0"))
    
    openai_api_key = os.getenv("OPENAI_API_KEY")
    anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
    provider = os.getenv("LLM_PROVIDER", "ollama")
    
    # Create service instance
    service = LLMService(
        ollama_base_url=ollama_base_url,
        model_name=model_name,
        base_timeout=base_timeout,
        openai_api_key=openai_api_key,
        anthropic_api_key=anthropic_api_key,
        provider=provider
    )
    
    return service


# Singleton instance (for backward compatibility during migration)
_llm_service_instance: Optional[object] = None


def get_llm_service_singleton():
    """
    Get or create singleton LLMService instance.
    This is provided for backward compatibility during migration.
    New code should use dependency injection instead.
    
    Returns:
        LLMService singleton instance
    """
    global _llm_service_instance
    if _llm_service_instance is None:
        _llm_service_instance = create_llm_service()
    return _llm_service_instance