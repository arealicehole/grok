"""Base classes for LLM providers."""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from pydantic import BaseModel
import asyncio
import logging

logger = logging.getLogger(__name__)


class LLMProviderError(Exception):
    """Base exception for LLM provider errors."""
    
    def __init__(self, message: str, recoverable: bool = True, provider: str = "unknown"):
        super().__init__(message)
        self.message = message
        self.recoverable = recoverable
        self.provider = provider


class LLMResponse(BaseModel):
    """Standardized response from LLM providers."""
    content: str
    tokens_used: int = 0
    provider: str
    model: str
    processing_time_ms: int = 0
    metadata: Dict[str, Any] = {}


class ProviderHealth(BaseModel):
    """Health status of an LLM provider."""
    available: bool
    response_time_ms: Optional[int] = None
    models_available: List[str] = []
    error_message: Optional[str] = None


class LLMProvider(ABC):
    """Abstract base class for all LLM providers."""

    def __init__(self, name: str, base_url: str):
        self.name = name
        self.base_url = base_url
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    @abstractmethod
    async def generate_completion(
        self,
        prompt: str,
        model: str,
        temperature: float = 0.2,
        max_tokens: int = 2000,
        timeout_seconds: int = 30,
        **kwargs
    ) -> LLMResponse:
        """Generate completion using the provider's API."""
        pass

    @abstractmethod
    async def list_available_models(self) -> List[str]:
        """List models available on this provider."""
        pass

    @abstractmethod
    async def check_health(self) -> ProviderHealth:
        """Check if provider is available and responsive."""
        pass

    async def is_available(self) -> bool:
        """Simple availability check."""
        try:
            health = await self.check_health()
            return health.available
        except Exception:
            return False

    def _log_request(self, model: str, prompt_length: int, **kwargs):
        """Log outgoing request for debugging."""
        self.logger.debug(
            f"Request to {self.name}: model={model}, prompt_length={prompt_length}, "
            f"temperature={kwargs.get('temperature', 'default')}, "
            f"max_tokens={kwargs.get('max_tokens', 'default')}"
        )

    def _log_response(self, response: LLMResponse):
        """Log response for debugging and monitoring."""
        self.logger.debug(
            f"Response from {self.name}: tokens={response.tokens_used}, "
            f"time={response.processing_time_ms}ms, "
            f"content_length={len(response.content)}"
        )

    def _log_error(self, error: Exception, context: str = ""):
        """Log errors with context."""
        self.logger.error(
            f"Error in {self.name} {context}: {type(error).__name__}: {error}"
        )