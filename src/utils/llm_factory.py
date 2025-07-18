"""LLM Factory for creating configured LLM instances using LiteLLM."""

import os
from typing import List, Optional, Dict, Any, AsyncGenerator
from abc import ABC, abstractmethod
import requests
from tenacity import retry, stop_after_attempt, wait_exponential

from langchain_litellm import ChatLiteLLM
from langchain_core.callbacks import AsyncCallbackHandler
from langchain_core.messages import BaseMessage
from langchain_anthropic import ChatAnthropic


class LLMError(Exception):
    """Base exception for LLM-related errors."""

    pass


class LLMRateLimitError(LLMError):
    """Raised when rate limit is hit."""

    pass


class LLMTimeoutError(LLMError):
    """Raised when LLM call times out."""

    pass


class LLMValidationError(LLMError):
    """Raised when LLM configuration is invalid."""

    pass


class LLMFactory:
    """Factory for creating configured LLM instances."""

    @staticmethod
    def create_orchestrator_llm():
        """Create LLM for the main orchestrator agent with fallback."""
        # Try LiteLLM first
        try:
            return LLMFactory._create_litellm_orchestrator()
        except Exception as e:
            # Silently fall back to direct Anthropic
            try:
                return LLMFactory._create_anthropic_orchestrator()
            except Exception as e2:
                # If both fail, raise the Anthropic error
                raise e2

    @staticmethod
    def _create_litellm_orchestrator() -> ChatLiteLLM:
        """Create LiteLLM orchestrator."""
        api_key = os.getenv("LITELLM_API_KEY")
        api_base = os.getenv("LITELLM_BASE_URL")

        if not api_key or not api_base:
            raise LLMValidationError("LiteLLM credentials not available")

        return ChatLiteLLM(
            model="anthropic/claude-3-sonnet-20240229",  # Fast model for orchestration
            api_key=api_key,
            api_base=api_base,
            temperature=0.3,  # Lower temperature for consistent routing
            max_tokens=1024,
            timeout=30,
        )

    @staticmethod
    def _create_anthropic_orchestrator() -> ChatAnthropic:
        """Create direct Anthropic orchestrator."""
        api_key = os.getenv("ANTHROPIC_AUTH_TOKEN")
        
        if not api_key:
            raise LLMValidationError("ANTHROPIC_AUTH_TOKEN environment variable is required")

        return ChatAnthropic(
            model="claude-3-5-sonnet-20241022",  # Updated model name
            api_key=api_key,
            temperature=0.3,
            max_tokens=1024,
            timeout=30,
        )

    @staticmethod
    def create_planner_llm() -> ChatLiteLLM:
        """Create LLM for the planning agent."""
        api_key = os.getenv("LITELLM_API_KEY")
        api_base = os.getenv("LITELLM_BASE_URL")

        if not api_key:
            raise LLMValidationError("LITELLM_API_KEY environment variable is required")

        if not api_base:
            raise LLMValidationError(
                "LITELLM_BASE_URL environment variable is required"
            )

        return ChatLiteLLM(
            model="anthropic/claude-3-opus-20240229",  # More capable model for complex planning
            api_key=api_key,
            api_base=api_base,
            temperature=0.1,  # Very low temperature for structured planning
            max_tokens=2048,
            timeout=45,
        )

    @staticmethod
    def create_tool_llm() -> ChatLiteLLM:
        """Create LLM for tool-specific tasks."""
        api_key = os.getenv("LITELLM_API_KEY")
        api_base = os.getenv("LITELLM_BASE_URL")

        if not api_key:
            raise LLMValidationError("LITELLM_API_KEY environment variable is required")

        if not api_base:
            raise LLMValidationError(
                "LITELLM_BASE_URL environment variable is required"
            )

        return ChatLiteLLM(
            model="anthropic/claude-3-haiku-20240307",  # Fastest model for simple tool calls
            api_key=api_key,
            api_base=api_base,
            temperature=0.0,  # Deterministic for tool operations
            max_tokens=512,
            timeout=20,
        )

    @staticmethod
    def create_result_formatter_llm():
        """Create LLM for formatting search results with fallback."""
        # Try LiteLLM first
        try:
            return LLMFactory._create_litellm_formatter()
        except Exception as e:
            # Silently fall back to direct Anthropic
            try:
                return LLMFactory._create_anthropic_formatter()
            except Exception as e2:
                # If both fail, raise the Anthropic error
                raise e2

    @staticmethod
    def _create_litellm_formatter() -> ChatLiteLLM:
        """Create LiteLLM formatter."""
        api_key = os.getenv("LITELLM_API_KEY")
        api_base = os.getenv("LITELLM_BASE_URL")

        if not api_key or not api_base:
            raise LLMValidationError("LiteLLM credentials not available")

        return ChatLiteLLM(
            model="anthropic/claude-3-haiku-20240307",  # Fast model for formatting
            api_key=api_key,
            api_base=api_base,
            temperature=0.2,  # Some creativity for formatting
            max_tokens=2048,
            timeout=30,
        )

    @staticmethod
    def _create_anthropic_formatter() -> ChatAnthropic:
        """Create direct Anthropic formatter."""
        api_key = os.getenv("ANTHROPIC_AUTH_TOKEN")
        
        if not api_key:
            raise LLMValidationError("ANTHROPIC_AUTH_TOKEN environment variable is required")

        return ChatAnthropic(
            model="claude-3-5-haiku-20241022",  # Updated model name
            api_key=api_key,
            temperature=0.2,
            max_tokens=2048,
            timeout=30,
        )

    @staticmethod
    def create_summary_llm() -> ChatLiteLLM:
        """Create LLM for summarization tasks."""
        api_key = os.getenv("LITELLM_API_KEY")
        api_base = os.getenv("LITELLM_BASE_URL")

        if not api_key:
            raise LLMValidationError("LITELLM_API_KEY environment variable is required")

        if not api_base:
            raise LLMValidationError(
                "LITELLM_BASE_URL environment variable is required"
            )

        return ChatLiteLLM(
            model="anthropic/claude-3-haiku-20240307",  # Fast model for summaries
            api_key=api_key,
            api_base=api_base,
            temperature=0.2,  # Slight creativity for summaries
            max_tokens=1024,
            timeout=30,
        )


class LiteLLMHelper:
    """Helper utilities for LiteLLM operations."""

    @staticmethod
    def get_available_models() -> Optional[List[str]]:
        """Get list of available models from LiteLLM proxy."""
        api_key = os.getenv("LITELLM_API_KEY")
        base_url = os.getenv("LITELLM_BASE_URL")

        if not api_key or not base_url:
            return None

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        try:
            response = requests.get(f"{base_url}/models", headers=headers, timeout=10)

            if response.status_code == 200:
                models = response.json()
                return [model["id"] for model in models["data"]]
            return None
        except Exception:
            return None

    @staticmethod
    def validate_model_availability(model_name: str) -> bool:
        """Check if a specific model is available."""
        available_models = LiteLLMHelper.get_available_models()
        return available_models is not None and model_name in available_models

    @staticmethod
    def validate_configuration() -> Dict[str, Any]:
        """Validate LiteLLM configuration and return status."""
        api_key = os.getenv("LITELLM_API_KEY")
        base_url = os.getenv("LITELLM_BASE_URL")

        result = {"valid": False, "errors": [], "available_models": None}

        if not api_key:
            result["errors"].append("LITELLM_API_KEY environment variable is missing")

        if not base_url:
            result["errors"].append("LITELLM_BASE_URL environment variable is missing")

        if api_key and base_url:
            try:
                models = LiteLLMHelper.get_available_models()
                if models is not None:
                    result["valid"] = True
                    result["available_models"] = models
                else:
                    result["errors"].append("Unable to connect to LiteLLM proxy")
            except Exception as e:
                result["errors"].append(f"Connection error: {str(e)}")

        return result


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10),
    reraise=True,
)
async def safe_llm_call(llm: ChatLiteLLM, messages: List[Dict]) -> str:
    """Wrapper for LLM calls with retry logic."""
    try:
        response = await llm.apredict_messages(messages)
        return response.content
    except Exception as e:
        error_str = str(e).lower()
        if "rate_limit" in error_str or "429" in error_str:
            raise LLMRateLimitError(f"Rate limit hit: {e}")
        elif "timeout" in error_str or "504" in error_str:
            raise LLMTimeoutError(f"LLM call timed out: {e}")
        else:
            raise LLMError(f"LLM call failed: {e}")


async def stream_llm_response(
    llm: ChatLiteLLM,
    messages: List[Dict[str, str]],
    callback_handler: Optional[AsyncCallbackHandler] = None,
) -> AsyncGenerator[str, None]:
    """Stream responses from LLM for real-time updates."""
    callbacks = [callback_handler] if callback_handler else []

    try:
        async for chunk in llm.astream(messages, callbacks=callbacks):
            if hasattr(chunk, "content") and chunk.content:
                yield chunk.content
    except Exception as e:
        error_str = str(e).lower()
        if "rate_limit" in error_str or "429" in error_str:
            raise LLMRateLimitError(f"Rate limit hit during streaming: {e}")
        elif "timeout" in error_str or "504" in error_str:
            raise LLMTimeoutError(f"LLM streaming timed out: {e}")
        else:
            raise LLMError(f"LLM streaming failed: {e}")


class LLMManager:
    """Manager for LLM instances with connection pooling and caching."""

    def __init__(self):
        self._orchestrator_llm = None
        self._planner_llm = None
        self._tool_llm = None
        self._summary_llm = None

    def get_orchestrator_llm(self) -> ChatLiteLLM:
        """Get or create orchestrator LLM instance."""
        if self._orchestrator_llm is None:
            self._orchestrator_llm = LLMFactory.create_orchestrator_llm()
        return self._orchestrator_llm

    def get_planner_llm(self) -> ChatLiteLLM:
        """Get or create planner LLM instance."""
        if self._planner_llm is None:
            self._planner_llm = LLMFactory.create_planner_llm()
        return self._planner_llm

    def get_tool_llm(self) -> ChatLiteLLM:
        """Get or create tool LLM instance."""
        if self._tool_llm is None:
            self._tool_llm = LLMFactory.create_tool_llm()
        return self._tool_llm

    def get_summary_llm(self) -> ChatLiteLLM:
        """Get or create summary LLM instance."""
        if self._summary_llm is None:
            self._summary_llm = LLMFactory.create_summary_llm()
        return self._summary_llm

    def reset_connections(self):
        """Reset all LLM connections."""
        self._orchestrator_llm = None
        self._planner_llm = None
        self._tool_llm = None
        self._summary_llm = None
