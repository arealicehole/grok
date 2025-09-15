"""OpenRouter provider for cloud LLM integration."""

import asyncio
import json
import time
import logging
from typing import Dict, Any, List, Optional
import aiohttp
from aiohttp import ClientTimeout, ClientError

from .base import LLMProvider, LLMProviderError, LLMResponse, ProviderHealth


logger = logging.getLogger(__name__)


class OpenRouterProvider(LLMProvider):
    """Cloud provider for advanced models via OpenRouter API."""

    # Popular models with pricing (as of 2025)
    POPULAR_MODELS = {
        "openai/gpt-4o": {"description": "GPT-4 Optimized", "context": 128000},
        "openai/gpt-4o-mini": {"description": "GPT-4 Optimized Mini", "context": 128000},
        "anthropic/claude-3.5-sonnet": {"description": "Claude 3.5 Sonnet", "context": 200000},
        "anthropic/claude-3-haiku": {"description": "Claude 3 Haiku (fast)", "context": 200000},
        "google/gemini-pro-1.5": {"description": "Gemini Pro 1.5", "context": 1000000},
        "meta-llama/llama-3.1-70b-instruct": {"description": "Llama 3.1 70B", "context": 131072},
        "mistralai/mistral-large": {"description": "Mistral Large", "context": 128000},
        "cohere/command-r-plus": {"description": "Command R+", "context": 128000},
    }

    def __init__(
        self, 
        api_key: str,
        base_url: str = "https://openrouter.ai/api/v1",
        app_name: Optional[str] = "grok-intelligence-engine",
        app_url: Optional[str] = None
    ):
        super().__init__("openrouter", base_url)
        self.api_key = api_key
        self.app_name = app_name
        self.app_url = app_url
        self._session: Optional[aiohttp.ClientSession] = None
        self._request_count = 0
        self._total_tokens_used = 0
        self._total_cost = 0.0  # Track estimated costs

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session with authentication."""
        if self._session is None or self._session.closed:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            # Add app attribution headers if provided
            if self.app_url:
                headers["HTTP-Referer"] = self.app_url
            if self.app_name:
                headers["X-Title"] = self.app_name
            
            self._session = aiohttp.ClientSession(
                timeout=ClientTimeout(total=60),
                headers=headers
            )
        return self._session

    async def close(self):
        """Close HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    async def generate_completion(
        self,
        prompt: str,
        model: str,
        temperature: float = 0.2,
        max_tokens: int = 2000,
        timeout_seconds: int = 30,
        **kwargs
    ) -> LLMResponse:
        """Generate completion using OpenRouter API."""
        start_time = time.time()
        
        try:
            self._log_request(model, len(prompt), temperature=temperature, max_tokens=max_tokens)
            self._request_count += 1

            session = await self._get_session()
            
            # OpenRouter uses OpenAI-compatible format
            messages = [{"role": "user", "content": prompt}]
            
            # Add system message if provided
            if "system" in kwargs:
                messages.insert(0, {"role": "system", "content": kwargs["system"]})

            # Build request payload
            payload = {
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "stream": False  # Non-streaming for simplicity
            }

            # Add optional parameters
            if "stop" in kwargs:
                payload["stop"] = kwargs["stop"]
            if "top_p" in kwargs:
                payload["top_p"] = kwargs["top_p"]
            if "frequency_penalty" in kwargs:
                payload["frequency_penalty"] = kwargs["frequency_penalty"]
            if "presence_penalty" in kwargs:
                payload["presence_penalty"] = kwargs["presence_penalty"]

            async with session.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                timeout=ClientTimeout(total=timeout_seconds)
            ) as response:
                
                # Handle rate limiting
                if response.status == 429:
                    retry_after = response.headers.get("Retry-After", "60")
                    raise LLMProviderError(
                        f"Rate limited. Retry after {retry_after} seconds",
                        recoverable=True,
                        provider="openrouter"
                    )
                
                if response.status != 200:
                    error_text = await response.text()
                    
                    # Try to parse error JSON
                    try:
                        error_data = json.loads(error_text)
                        error_message = error_data.get("error", {}).get("message", error_text)
                    except:
                        error_message = error_text
                    
                    raise LLMProviderError(
                        f"OpenRouter API error: HTTP {response.status} - {error_message}",
                        recoverable=response.status >= 500,
                        provider="openrouter"
                    )

                data = await response.json()
                
                # Extract response content (OpenAI format)
                choices = data.get("choices", [])
                if not choices:
                    raise LLMProviderError(
                        "OpenRouter returned no choices",
                        recoverable=True,
                        provider="openrouter"
                    )
                
                content = choices[0].get("message", {}).get("content", "")
                if not content:
                    raise LLMProviderError(
                        "OpenRouter returned empty response",
                        recoverable=True,
                        provider="openrouter"
                    )

                # Extract usage information
                usage = data.get("usage", {})
                total_tokens = usage.get("total_tokens", 0)
                prompt_tokens = usage.get("prompt_tokens", 0)
                completion_tokens = usage.get("completion_tokens", 0)
                
                # Track usage
                self._total_tokens_used += total_tokens
                
                # Calculate processing time
                processing_time_ms = int((time.time() - start_time) * 1000)

                # Build response
                llm_response = LLMResponse(
                    content=content,
                    tokens_used=total_tokens,
                    provider="openrouter",
                    model=model,
                    processing_time_ms=processing_time_ms,
                    metadata={
                        "prompt_tokens": prompt_tokens,
                        "completion_tokens": completion_tokens,
                        "finish_reason": choices[0].get("finish_reason", "unknown"),
                        "model_used": data.get("model", model),  # Actual model used (may differ)
                        "generation_id": data.get("id"),
                        "request_count": self._request_count,
                        "total_tokens_used": self._total_tokens_used
                    }
                )

                self._log_response(llm_response)
                return llm_response

        except asyncio.TimeoutError:
            error = LLMProviderError(
                f"OpenRouter request timeout after {timeout_seconds}s",
                recoverable=True,
                provider="openrouter"
            )
            self._log_error(error, "timeout")
            raise error

        except ClientError as e:
            error = LLMProviderError(
                f"OpenRouter connection error: {e}",
                recoverable=True,
                provider="openrouter"
            )
            self._log_error(error, "connection")
            raise error

        except json.JSONDecodeError as e:
            error = LLMProviderError(
                f"OpenRouter returned invalid JSON: {e}",
                recoverable=False,
                provider="openrouter"
            )
            self._log_error(error, "json_decode")
            raise error

        except Exception as e:
            error = LLMProviderError(
                f"Unexpected OpenRouter error: {e}",
                recoverable=False,
                provider="openrouter"
            )
            self._log_error(error, "unexpected")
            raise error

    async def list_available_models(self) -> List[str]:
        """List popular models available on OpenRouter."""
        # For now, return hardcoded popular models
        # In production, this could query the OpenRouter models endpoint
        models = list(self.POPULAR_MODELS.keys())
        self.logger.info(f"Available OpenRouter models: {models}")
        return models

    async def check_health(self) -> ProviderHealth:
        """Check if OpenRouter API is accessible with valid credentials."""
        start_time = time.time()
        
        try:
            session = await self._get_session()

            # Test with a minimal completion request
            payload = {
                "model": "openai/gpt-4o-mini",  # Use cheapest model for health check
                "messages": [{"role": "user", "content": "test"}],
                "max_tokens": 1,
                "stream": False
            }

            async with session.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                timeout=ClientTimeout(total=5)
            ) as response:
                
                response_time_ms = int((time.time() - start_time) * 1000)
                
                if response.status == 401:
                    return ProviderHealth(
                        available=False,
                        response_time_ms=response_time_ms,
                        error_message="Invalid API key"
                    )
                
                if response.status == 200:
                    # Get available models
                    models = await self.list_available_models()
                    return ProviderHealth(
                        available=True,
                        response_time_ms=response_time_ms,
                        models_available=models
                    )
                else:
                    return ProviderHealth(
                        available=False,
                        response_time_ms=response_time_ms,
                        error_message=f"HTTP {response.status}"
                    )

        except asyncio.TimeoutError:
            return ProviderHealth(
                available=False,
                error_message="Connection timeout"
            )

        except ClientError as e:
            return ProviderHealth(
                available=False,
                error_message=f"Connection error: {e}"
            )

        except Exception as e:
            return ProviderHealth(
                available=False,
                error_message=f"Health check failed: {e}"
            )

    def get_usage_stats(self) -> Dict[str, Any]:
        """Get usage statistics for this session."""
        return {
            "request_count": self._request_count,
            "total_tokens_used": self._total_tokens_used,
            "estimated_cost_usd": self._total_cost,
            "provider": "openrouter"
        }

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()