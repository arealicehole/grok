"""Model selection and provider management."""

import asyncio
import logging
from typing import Dict, List, Optional, Any
from app.models.profile import ModelConfig
from .base import LLMProvider, LLMProviderError, LLMResponse


logger = logging.getLogger(__name__)


class ModelSelector:
    """Intelligent model selection with fallback strategies."""

    def __init__(self, providers: Dict[str, LLMProvider]):
        self.providers = providers
        self.fallback_order = ["local", "openrouter"]  # Default fallback order
        self.logger = logging.getLogger(__name__)

    async def select_provider(
        self, 
        config: ModelConfig,
        global_overrides: Optional[Dict[str, Any]] = None
    ) -> LLMProvider:
        """Select best available provider with fallbacks."""

        # Apply global overrides
        effective_config = config.model_copy()
        if global_overrides:
            if "force_provider" in global_overrides:
                effective_config.provider = global_overrides["force_provider"]
            if "force_model" in global_overrides:
                effective_config.model = global_overrides["force_model"]

        # Try preferred provider first
        preferred_provider = self.providers.get(effective_config.provider)
        if preferred_provider:
            try:
                is_available = await preferred_provider.is_available()
                if is_available:
                    self.logger.info(f"Using preferred provider: {effective_config.provider}")
                    return preferred_provider
                else:
                    self.logger.warning(
                        f"Preferred provider {effective_config.provider} is not available"
                    )
            except Exception as e:
                self.logger.warning(
                    f"Error checking preferred provider {effective_config.provider}: {e}"
                )

        # Fallback to available providers
        for provider_name in self.fallback_order:
            if provider_name == effective_config.provider:
                continue  # Already tried

            fallback_provider = self.providers.get(provider_name)
            if fallback_provider:
                try:
                    is_available = await fallback_provider.is_available()
                    if is_available:
                        self.logger.warning(
                            f"Falling back from {effective_config.provider} to {provider_name}"
                        )
                        # Update config to reflect the fallback
                        effective_config.provider = provider_name
                        return fallback_provider
                except Exception as e:
                    self.logger.warning(
                        f"Error checking fallback provider {provider_name}: {e}"
                    )

        # No providers available
        available_providers = list(self.providers.keys())
        raise LLMProviderError(
            f"No available LLM providers. Configured: {available_providers}, "
            f"Preferred: {config.provider}, Fallbacks: {self.fallback_order}",
            recoverable=True,
            provider="selector"
        )

    async def generate_completion(
        self,
        prompt: str,
        config: ModelConfig,
        global_overrides: Optional[Dict[str, Any]] = None
    ) -> LLMResponse:
        """Generate completion using selected provider with configuration."""

        # Select provider
        provider = await self.select_provider(config, global_overrides)

        # Apply any global parameter overrides
        effective_config = config.model_copy()
        if global_overrides:
            for param in ["temperature", "max_tokens", "timeout_seconds"]:
                global_key = f"global_{param}"
                if global_key in global_overrides:
                    setattr(effective_config, param, global_overrides[global_key])

        # Generate completion
        try:
            response = await provider.generate_completion(
                prompt=prompt,
                model=effective_config.model,
                temperature=effective_config.temperature,
                max_tokens=effective_config.max_tokens,
                timeout_seconds=effective_config.timeout_seconds
            )
            
            self.logger.info(
                f"Completion generated: provider={response.provider}, "
                f"model={response.model}, tokens={response.tokens_used}, "
                f"time={response.processing_time_ms}ms"
            )
            
            return response

        except Exception as e:
            self.logger.error(
                f"Completion failed with provider {provider.name}: {e}"
            )
            raise

    async def get_provider_status(self) -> Dict[str, Dict[str, Any]]:
        """Get health status of all configured providers."""
        status = {}
        
        for name, provider in self.providers.items():
            try:
                health = await provider.check_health()
                status[name] = {
                    "available": health.available,
                    "response_time_ms": health.response_time_ms,
                    "models_count": len(health.models_available),
                    "models": health.models_available[:5],  # Limit for response size
                    "error": health.error_message
                }
            except Exception as e:
                status[name] = {
                    "available": False,
                    "error": f"Health check failed: {e}"
                }
        
        return status

    async def close_all(self):
        """Close all provider connections."""
        for provider in self.providers.values():
            try:
                if hasattr(provider, 'close'):
                    await provider.close()
            except Exception as e:
                self.logger.warning(f"Error closing provider {provider.name}: {e}")