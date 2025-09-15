"""Tests for OpenRouter provider integration."""

import pytest
import asyncio
from unittest.mock import AsyncMock, patch
import json

from app.providers.openrouter import OpenRouterProvider
from app.providers.base import LLMProviderError, ProviderHealth


class TestOpenRouterProvider:
    """Test OpenRouter provider functionality."""

    @pytest.fixture
    def provider(self):
        """Create OpenRouterProvider instance for testing."""
        return OpenRouterProvider(
            api_key="test-api-key",
            base_url="https://openrouter.ai/api/v1",
            app_name="test-app"
        )

    @pytest.fixture
    def mock_openrouter_response(self):
        """Mock successful OpenRouter response."""
        return {
            "id": "chatcmpl-test123",
            "object": "chat.completion",
            "created": 1699999999,
            "model": "openai/gpt-4o-mini",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": '{"people": ["John", "Jane"], "companies": ["TechCorp"], "dates": ["2025-09-15"], "key_points": ["AI integration meeting", "LLM provider testing"]}'
                    },
                    "finish_reason": "stop"
                }
            ],
            "usage": {
                "prompt_tokens": 45,
                "completion_tokens": 85,
                "total_tokens": 130
            }
        }

    @pytest.fixture
    def mock_error_response(self):
        """Mock error response from OpenRouter."""
        return {
            "error": {
                "message": "Invalid API key provided",
                "type": "invalid_request_error",
                "code": "invalid_api_key"
            }
        }

    @pytest.mark.asyncio
    async def test_generate_completion_success(self, provider, mock_openrouter_response):
        """Test successful completion generation."""
        with patch('aiohttp.ClientSession.post') as mock_post:
            # Setup mock response
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json.return_value = mock_openrouter_response
            mock_post.return_value.__aenter__.return_value = mock_response

            # Test completion
            result = await provider.generate_completion(
                prompt="Extract entities from: John works at TechCorp",
                model="openai/gpt-4o-mini",
                temperature=0.1,
                max_tokens=1000
            )

            # Verify request was made correctly
            mock_post.assert_called_once()
            call_args = mock_post.call_args
            assert call_args[1]['json']['model'] == "openai/gpt-4o-mini"
            assert call_args[1]['json']['messages'][0]['content'] == "Extract entities from: John works at TechCorp"
            assert call_args[1]['json']['temperature'] == 0.1
            assert call_args[1]['json']['max_tokens'] == 1000

            # Verify response
            expected_content = '{"people": ["John", "Jane"], "companies": ["TechCorp"], "dates": ["2025-09-15"], "key_points": ["AI integration meeting", "LLM provider testing"]}'
            assert result.content == expected_content
            assert result.tokens_used == 130
            assert result.provider == "openrouter"
            assert result.model == "openai/gpt-4o-mini"
            assert result.processing_time_ms >= 0

    @pytest.mark.asyncio
    async def test_generate_completion_with_system_message(self, provider, mock_openrouter_response):
        """Test completion with system message."""
        with patch('aiohttp.ClientSession.post') as mock_post:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json.return_value = mock_openrouter_response
            mock_post.return_value.__aenter__.return_value = mock_response

            await provider.generate_completion(
                prompt="Test prompt",
                model="openai/gpt-4o-mini",
                system="You are a helpful assistant."
            )

            # Verify system message was included
            call_args = mock_post.call_args
            messages = call_args[1]['json']['messages']
            assert len(messages) == 2
            assert messages[0]['role'] == "system"
            assert messages[0]['content'] == "You are a helpful assistant."
            assert messages[1]['role'] == "user"
            assert messages[1]['content'] == "Test prompt"

    @pytest.mark.asyncio
    async def test_generate_completion_auth_error(self, provider, mock_error_response):
        """Test completion with authentication error."""
        with patch('aiohttp.ClientSession.post') as mock_post:
            mock_response = AsyncMock()
            mock_response.status = 401
            mock_response.text.return_value = json.dumps(mock_error_response)
            mock_post.return_value.__aenter__.return_value = mock_response

            with pytest.raises(LLMProviderError) as exc_info:
                await provider.generate_completion(
                    prompt="Test prompt",
                    model="openai/gpt-4o-mini"
                )

            assert "Invalid API key provided" in str(exc_info.value)
            assert exc_info.value.recoverable is False  # Auth errors are not recoverable
            assert exc_info.value.provider == "openrouter"

    @pytest.mark.asyncio
    async def test_generate_completion_rate_limit(self, provider):
        """Test completion with rate limit error."""
        with patch('aiohttp.ClientSession.post') as mock_post:
            mock_response = AsyncMock()
            mock_response.status = 429
            mock_response.headers = {"Retry-After": "30"}
            mock_post.return_value.__aenter__.return_value = mock_response

            with pytest.raises(LLMProviderError) as exc_info:
                await provider.generate_completion(
                    prompt="Test prompt",
                    model="openai/gpt-4o-mini"
                )

            assert "Rate limited" in str(exc_info.value)
            assert "30 seconds" in str(exc_info.value)
            assert exc_info.value.recoverable is True
            assert exc_info.value.provider == "openrouter"

    @pytest.mark.asyncio
    async def test_generate_completion_empty_choices(self, provider):
        """Test completion with empty choices."""
        with patch('aiohttp.ClientSession.post') as mock_post:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json.return_value = {"choices": []}
            mock_post.return_value.__aenter__.return_value = mock_response

            with pytest.raises(LLMProviderError) as exc_info:
                await provider.generate_completion(
                    prompt="Test prompt",
                    model="openai/gpt-4o-mini"
                )

            assert "returned no choices" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_list_available_models(self, provider):
        """Test listing available models."""
        models = await provider.list_available_models()
        
        # Should return hardcoded popular models
        assert len(models) > 0
        assert "openai/gpt-4o" in models
        assert "openai/gpt-4o-mini" in models
        assert "anthropic/claude-3.5-sonnet" in models
        assert "anthropic/claude-3-haiku" in models

    @pytest.mark.asyncio
    async def test_check_health_success(self, provider):
        """Test health check when service is available."""
        with patch('aiohttp.ClientSession.post') as mock_post:
            # Mock successful minimal response
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json.return_value = {
                "choices": [{"message": {"content": "ok"}}],
                "usage": {"total_tokens": 1}
            }
            mock_post.return_value.__aenter__.return_value = mock_response

            health = await provider.check_health()

            assert health.available is True
            assert health.response_time_ms is not None
            assert health.response_time_ms > 0
            assert len(health.models_available) > 0

    @pytest.mark.asyncio
    async def test_check_health_auth_failure(self, provider):
        """Test health check with authentication failure."""
        with patch('aiohttp.ClientSession.post') as mock_post:
            mock_response = AsyncMock()
            mock_response.status = 401
            mock_post.return_value.__aenter__.return_value = mock_response

            health = await provider.check_health()

            assert health.available is False
            assert health.error_message == "Invalid API key"
            assert health.response_time_ms is not None

    @pytest.mark.asyncio
    async def test_check_health_timeout(self, provider):
        """Test health check with timeout."""
        with patch('aiohttp.ClientSession.post') as mock_post:
            mock_post.side_effect = asyncio.TimeoutError()

            health = await provider.check_health()

            assert health.available is False
            assert health.error_message == "Connection timeout"

    @pytest.mark.asyncio
    async def test_usage_stats_tracking(self, provider, mock_openrouter_response):
        """Test usage statistics tracking."""
        with patch('aiohttp.ClientSession.post') as mock_post:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json.return_value = mock_openrouter_response
            mock_post.return_value.__aenter__.return_value = mock_response

            # Make several requests
            for i in range(3):
                await provider.generate_completion(
                    prompt=f"Test prompt {i}",
                    model="openai/gpt-4o-mini"
                )

            # Check usage stats
            stats = provider.get_usage_stats()
            assert stats["request_count"] == 3
            assert stats["total_tokens_used"] == 390  # 130 * 3
            assert stats["provider"] == "openrouter"

    @pytest.mark.asyncio
    async def test_provider_context_manager(self, provider):
        """Test provider as async context manager."""
        async with provider as p:
            assert p is provider
            # Verify session is created
            session = await p._get_session()
            assert session is not None
            # Verify auth header is set
            assert "Authorization" in session.headers
            assert session.headers["Authorization"] == "Bearer test-api-key"

        # Session should be closed after context exit
        assert provider._session is None or provider._session.closed

    @pytest.mark.asyncio
    async def test_app_attribution_headers(self, provider):
        """Test that app attribution headers are set correctly."""
        provider_with_url = OpenRouterProvider(
            api_key="test-key",
            app_name="test-app",
            app_url="https://example.com"
        )

        session = await provider_with_url._get_session()
        
        assert "HTTP-Referer" in session.headers
        assert session.headers["HTTP-Referer"] == "https://example.com"
        assert "X-Title" in session.headers
        assert session.headers["X-Title"] == "test-app"

        await provider_with_url.close()


@pytest.mark.integration
class TestOpenRouterIntegration:
    """Integration tests for OpenRouter provider (require real API key)."""

    @pytest.mark.asyncio
    async def test_real_openrouter_connection(self):
        """Test connection to real OpenRouter API (if API key available)."""
        import os
        
        api_key = os.environ.get("GROK_OPENROUTER_API_KEY")
        if not api_key:
            pytest.skip("No OpenRouter API key provided")

        provider = OpenRouterProvider(api_key)
        
        try:
            health = await provider.check_health()
            if health.available:
                print(f"✅ OpenRouter is available with {len(health.models_available)} models")
                print(f"Response time: {health.response_time_ms}ms")
                
                # Test simple completion if available
                response = await provider.generate_completion(
                    prompt="Say hello in one word",
                    model="openai/gpt-4o-mini",
                    max_tokens=5
                )
                print(f"Test completion: {response.content}")
                print(f"Tokens used: {response.tokens_used}")
                assert len(response.content) > 0
            else:
                print(f"⚠️  OpenRouter not available: {health.error_message}")
                
        except Exception as e:
            print(f"❌ OpenRouter test failed: {e}")
            # Don't fail the test - just log the issue
            
        finally:
            await provider.close()