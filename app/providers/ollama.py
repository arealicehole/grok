"""Ollama provider for local LLM integration."""

import asyncio
import json
import time
from typing import Dict, Any, List, Optional
import aiohttp
from aiohttp import ClientTimeout, ClientError

from .base import LLMProvider, LLMProviderError, LLMResponse, ProviderHealth


class OllamaProvider(LLMProvider):
    """Local Ollama provider for privacy-focused processing."""

    def __init__(self, base_url: str = "http://host.docker.internal:11434"):
        super().__init__("ollama", base_url)
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=ClientTimeout(total=60),
                headers={"Content-Type": "application/json"}
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
        """Generate completion using local Ollama instance."""
        start_time = time.time()
        
        try:
            self._log_request(model, len(prompt), temperature=temperature, max_tokens=max_tokens)

            session = await self._get_session()
            
            # Ollama API payload
            payload = {
                "model": model,
                "prompt": prompt,
                "options": {
                    "temperature": temperature,
                    "num_predict": max_tokens,
                    "stop": kwargs.get("stop", [])
                },
                "stream": False  # Use non-streaming for simplicity
            }

            # Add system message if provided
            if "system" in kwargs:
                payload["system"] = kwargs["system"]

            async with session.post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=ClientTimeout(total=timeout_seconds)
            ) as response:
                
                if response.status != 200:
                    error_text = await response.text()
                    raise LLMProviderError(
                        f"Ollama API error: HTTP {response.status} - {error_text}",
                        recoverable=response.status >= 500,
                        provider="ollama"
                    )

                data = await response.json()
                
                # Extract response content
                content = data.get("response", "")
                if not content:
                    raise LLMProviderError(
                        "Ollama returned empty response",
                        recoverable=True,
                        provider="ollama"
                    )

                # Calculate processing time
                processing_time_ms = int((time.time() - start_time) * 1000)

                # Build response
                llm_response = LLMResponse(
                    content=content,
                    tokens_used=data.get("eval_count", 0),
                    provider="ollama",
                    model=model,
                    processing_time_ms=processing_time_ms,
                    metadata={
                        "total_duration": data.get("total_duration", 0),
                        "load_duration": data.get("load_duration", 0),
                        "prompt_eval_count": data.get("prompt_eval_count", 0),
                        "prompt_eval_duration": data.get("prompt_eval_duration", 0),
                        "eval_duration": data.get("eval_duration", 0),
                        "context": data.get("context", [])
                    }
                )

                self._log_response(llm_response)
                return llm_response

        except asyncio.TimeoutError:
            error = LLMProviderError(
                f"Ollama request timeout after {timeout_seconds}s",
                recoverable=True,
                provider="ollama"
            )
            self._log_error(error, "timeout")
            raise error

        except ClientError as e:
            error = LLMProviderError(
                f"Ollama connection error: {e}",
                recoverable=True,
                provider="ollama"
            )
            self._log_error(error, "connection")
            raise error

        except json.JSONDecodeError as e:
            error = LLMProviderError(
                f"Ollama returned invalid JSON: {e}",
                recoverable=False,
                provider="ollama"
            )
            self._log_error(error, "json_decode")
            raise error

        except Exception as e:
            error = LLMProviderError(
                f"Unexpected Ollama error: {e}",
                recoverable=False,
                provider="ollama"
            )
            self._log_error(error, "unexpected")
            raise error

    async def list_available_models(self) -> List[str]:
        """List models available on local Ollama instance."""
        try:
            session = await self._get_session()

            async with session.get(f"{self.base_url}/api/tags") as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise LLMProviderError(
                        f"Failed to list Ollama models: HTTP {response.status} - {error_text}",
                        recoverable=response.status >= 500,
                        provider="ollama"
                    )

                data = await response.json()
                models = []
                
                for model_info in data.get("models", []):
                    model_name = model_info.get("name", "")
                    if model_name:
                        models.append(model_name)

                self.logger.info(f"Found {len(models)} Ollama models: {models}")
                return models

        except ClientError as e:
            error = LLMProviderError(
                f"Connection error listing Ollama models: {e}",
                recoverable=True,
                provider="ollama"
            )
            self._log_error(error, "list_models")
            raise error

        except Exception as e:
            error = LLMProviderError(
                f"Unexpected error listing Ollama models: {e}",
                recoverable=False,
                provider="ollama"
            )
            self._log_error(error, "list_models")
            raise error

    async def check_health(self) -> ProviderHealth:
        """Check if Ollama instance is available and responsive."""
        start_time = time.time()
        
        try:
            session = await self._get_session()

            # Test connection with tags endpoint
            async with session.get(
                f"{self.base_url}/api/tags",
                timeout=ClientTimeout(total=5)
            ) as response:
                
                response_time_ms = int((time.time() - start_time) * 1000)
                
                if response.status == 200:
                    # Try to get available models
                    try:
                        models = await self.list_available_models()
                        return ProviderHealth(
                            available=True,
                            response_time_ms=response_time_ms,
                            models_available=models
                        )
                    except Exception:
                        # Service is up but models might not be loaded
                        return ProviderHealth(
                            available=True,
                            response_time_ms=response_time_ms,
                            models_available=[],
                            error_message="Service available but no models found"
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

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()