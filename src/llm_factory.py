from typing import Dict, Any, Optional
import os
from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI
from langchain_xai import ChatXAI
from langchain_core.language_models.chat_models import BaseChatModel

class LLMFactory:
    """Factory class for creating LLM instances based on configuration"""
    
    @staticmethod
    def create_llm(config: Dict[str, Any]) -> BaseChatModel:
        """
        Create an LLM instance based on the provided configuration.
        
        Args:
            config: Dictionary containing LLM configuration with provider and settings
            
        Returns:
            An instance of a LangChain chat model
        """
        provider = config.get("provider", "anthropic").lower()
        settings = config.get("settings", {})
        
        if provider == "anthropic":
            return LLMFactory._create_anthropic(settings)
        elif provider == "openai":
            return LLMFactory._create_openai(settings)
        elif provider == "grok":
            return LLMFactory._create_grok(settings)
        else:
            raise ValueError(f"Unsupported LLM provider: {provider}")
    
    @staticmethod
    def _create_anthropic(settings: Dict[str, Any]) -> ChatAnthropic:
        """Create an Anthropic Claude instance"""
        kwargs = {
            "model": settings.get("model", "claude-3-sonnet-20240229"),
            "temperature": settings.get("temperature", 0),
            "max_tokens": settings.get("max_tokens", 4096),
            "anthropic_api_key": os.getenv("ANTHROPIC_API_KEY")
        }
        if "base_url" in settings:
            kwargs["anthropic_api_url"] = settings["base_url"]
        return ChatAnthropic(**kwargs)
    
    @staticmethod
    def _create_openai(settings: Dict[str, Any]) -> ChatOpenAI:
        """Create an OpenAI chat instance"""
        kwargs = {
            "model": settings.get("model", "gpt-4-turbo-preview"),
            "temperature": settings.get("temperature", 0),
            "max_tokens": settings.get("max_tokens", 4096),
            "openai_api_key": os.getenv("OPENAI_API_KEY"),
            "model_kwargs": {
                "response_format": {"type": "text"}  # Ensure text response format
            }
        }
        if "base_url" in settings:
            kwargs["base_url"] = settings["base_url"]
        return ChatOpenAI(**kwargs)
    
    @staticmethod
    def _create_grok(settings: Dict[str, Any]) -> ChatXAI:
        """Create a Grok chat instance using langchain-xai"""
        kwargs = {
            "model": settings.get("model", "grok-1"),  # Grok's default model
            "temperature": settings.get("temperature", 0),
            "max_tokens": settings.get("max_tokens", 4096),
            "xai_api_key": os.getenv("GROK_API_KEY")
        }
        if "base_url" in settings:
            kwargs["xai_base_url"] = settings["base_url"]
        return ChatXAI(**kwargs) 