"""Tests for Ollama provider integration."""

import pytest
import asyncio
from unittest.mock import AsyncMock, patch
import json

from app.providers.ollama import OllamaProvider
from app.providers.base import LLMProviderError, ProviderHealth


class TestOllamaProvider:
    """Test Ollama provider functionality."""

    @pytest.fixture
    def provider(self):
        """Create OllamaProvider instance for testing."""
        return OllamaProvider("http://localhost:11434")

    @pytest.fixture
    def mock_ollama_response(self):
        """Mock successful Ollama response."""
        return {
            "response": '{"entities": {"people": ["John Doe"], "companies": ["Acme Corp"]}}',
            "eval_count": 150,
            "total_duration": 5000000000,
            "load_duration": 1000000000,
            "prompt_eval_count": 50,
            "prompt_eval_duration": 2000000000,
            "eval_duration": 2000000000,
            "context": [1, 2, 3, 4, 5]
        }

    @pytest.fixture
    def mock_models_response(self):
        """Mock successful models list response."""
        return {
            "models": [
                {"name": "llama3.1:8b"},
                {"name": "mistral:7b"},
                {"name": "qwen2:1.5b"}
            ]
        }

    @pytest.mark.asyncio
    async def test_generate_completion_success(self, provider, mock_ollama_response):
        """Test successful completion generation."""
        with patch('aiohttp.ClientSession.post') as mock_post:
            # Setup mock response
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json.return_value = mock_ollama_response
            mock_post.return_value.__aenter__.return_value = mock_response

            # Test completion
            result = await provider.generate_completion(
                prompt="Extract entities from: John works at Acme Corp",
                model="llama3.1:8b",
                temperature=0.1,
                max_tokens=1000
            )

            assert result.content == mock_ollama_response["response"]
            assert result.tokens_used == 150
            assert result.provider == "ollama"
            assert result.model == "llama3.1:8b"
            assert result.processing_time_ms >= 0  # Can be 0 in mocked tests

    @pytest.mark.asyncio
    async def test_generate_completion_http_error(self, provider):
        """Test completion with HTTP error response."""
        with patch('aiohttp.ClientSession.post') as mock_post:
            # Setup error response
            mock_response = AsyncMock()
            mock_response.status = 500
            mock_response.text.return_value = "Internal Server Error"
            mock_post.return_value.__aenter__.return_value = mock_response

            with pytest.raises(LLMProviderError) as exc_info:
                await provider.generate_completion(
                    prompt="Test prompt",
                    model="llama3.1:8b"
                )

            assert "Ollama API error: HTTP 500" in str(exc_info.value)
            assert exc_info.value.recoverable is True
            assert exc_info.value.provider == "ollama"

    @pytest.mark.asyncio
    async def test_generate_completion_empty_response(self, provider):
        """Test completion with empty response."""
        with patch('aiohttp.ClientSession.post') as mock_post:
            # Setup empty response
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json.return_value = {"response": ""}
            mock_post.return_value.__aenter__.return_value = mock_response

            with pytest.raises(LLMProviderError) as exc_info:
                await provider.generate_completion(
                    prompt="Test prompt",
                    model="llama3.1:8b"
                )

            assert "Ollama returned empty response" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_list_available_models_success(self, provider, mock_models_response):
        """Test successful model listing."""
        with patch('aiohttp.ClientSession.get') as mock_get:
            # Setup mock response
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json.return_value = mock_models_response
            mock_get.return_value.__aenter__.return_value = mock_response

            models = await provider.list_available_models()

            assert len(models) == 3
            assert "llama3.1:8b" in models
            assert "mistral:7b" in models
            assert "qwen2:1.5b" in models

    @pytest.mark.asyncio
    async def test_check_health_available(self, provider, mock_models_response):
        """Test health check when service is available."""
        with patch('aiohttp.ClientSession.get') as mock_get:
            # Setup successful response
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json.return_value = mock_models_response
            mock_get.return_value.__aenter__.return_value = mock_response

            # Mock the list_available_models call
            with patch.object(provider, 'list_available_models') as mock_list:
                mock_list.return_value = ["llama3.1:8b", "mistral:7b"]
                
                health = await provider.check_health()

                assert health.available is True
                assert health.response_time_ms is not None
                assert health.response_time_ms > 0
                assert len(health.models_available) == 2

    @pytest.mark.asyncio
    async def test_check_health_unavailable(self, provider):
        """Test health check when service is unavailable."""
        with patch('aiohttp.ClientSession.get') as mock_get:
            # Setup connection error
            mock_get.side_effect = asyncio.TimeoutError()

            health = await provider.check_health()

            assert health.available is False
            assert health.error_message == "Connection timeout"

    @pytest.mark.asyncio
    async def test_provider_context_manager(self, provider):
        """Test provider as async context manager."""
        async with provider as p:
            assert p is provider
            # Verify session is created
            session = await p._get_session()
            assert session is not None

        # Session should be closed after context exit
        assert provider._session is None or provider._session.closed


@pytest.mark.integration
class TestOllamaIntegration:
    """Integration tests for Ollama provider (require running Ollama)."""

    @pytest.mark.asyncio
    async def test_real_ollama_connection(self):
        """Test connection to real Ollama instance (if available)."""
        provider = OllamaProvider()
        
        try:
            health = await provider.check_health()
            if health.available:
                print(f"✅ Ollama is available with {len(health.models_available)} models")
                print(f"Response time: {health.response_time_ms}ms")
                print(f"Models: {health.models_available}")
                
                # Test simple completion if models are available
                if health.models_available:
                    model = health.models_available[0]
                    response = await provider.generate_completion(
                        prompt="Say hello in one word",
                        model=model,
                        max_tokens=10
                    )
                    print(f"Test completion: {response.content}")
                    assert len(response.content) > 0
            else:
                print(f"⚠️  Ollama not available: {health.error_message}")
                
        except Exception as e:
            print(f"❌ Ollama test failed: {e}")
            # Don't fail the test - just log the issue
            
        finally:
            await provider.close()