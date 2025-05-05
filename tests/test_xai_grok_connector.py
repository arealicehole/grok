import pytest
import os
import time
from unittest.mock import patch, MagicMock, call
from openai import OpenAI, APIError, APIConnectionError, RateLimitError
from openai.types.chat import ChatCompletion, ChatCompletionMessage
from openai.types.chat.chat_completion import Choice
from openai.types.completion_usage import CompletionUsage
from openai.types.model import Model
from openai.types.models import ModelsPage # Correct type for models.list() return

# Make sure exceptions are importable
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

# Adjust the import path based on your project structure
# If tests/ is at the same level as src/, this should work
from src.xai_grok_connector import XaiGrokConnector
# Import custom exceptions
from src.exceptions import (
    XaiGrokError,
    XaiGrokConfigurationError,
    XaiGrokAuthenticationError,
    XaiGrokAPIError,
    XaiGrokNetworkError,
    XaiGrokRateLimitError,
    XaiGrokResponseError,
)

# --- Mock Data Fixtures (can be moved to conftest.py later) ---

@pytest.fixture
def mock_openai_client():
    """Provides a mocked OpenAI client instance."""
    mock_client = MagicMock(spec=OpenAI)
    
    # Mock models.list() response
    mock_models_page = MagicMock(spec=ModelsPage)
    mock_models_page.data = [MagicMock(spec=Model, id='grok-2-latest'), MagicMock(spec=Model, id='grok-1')]
    mock_client.models.list.return_value = mock_models_page

    # Mock chat.completions.create() response
    mock_usage = MagicMock(spec=CompletionUsage)
    mock_usage.prompt_tokens = 10
    mock_usage.completion_tokens = 20
    mock_usage.total_tokens = 30

    mock_message = MagicMock(spec=ChatCompletionMessage)
    mock_message.role = 'assistant'
    mock_message.content = 'Mocked response content'

    mock_choice = MagicMock(spec=Choice)
    mock_choice.index = 0
    mock_choice.message = mock_message
    mock_choice.finish_reason = 'stop'

    mock_completion = MagicMock(spec=ChatCompletion)
    mock_completion.id = 'chatcmpl-mockid123'
    mock_completion.object = 'chat.completion'
    mock_completion.created = 1677652288
    mock_completion.model = 'grok-2-latest'
    mock_completion.choices = [mock_choice]
    mock_completion.usage = mock_usage
    mock_client.chat.completions.create.return_value = mock_completion
    
    return mock_client

# --- Test Class ---

class TestXaiGrokConnector:

    # --- Initialization Tests ---
    @patch('src.xai_grok_connector.os.getenv')
    @patch('src.xai_grok_connector.OpenAI')
    def test_initialize_success_env_var(self, mock_openai_class, mock_getenv, mock_openai_client):
        """Test successful initialization using environment variable."""
        mock_getenv.return_value = "test_api_key_from_env"
        mock_openai_class.return_value = mock_openai_client
        
        connector = XaiGrokConnector()
        config = {}
        assert connector.initialize(config) is True
        assert connector.api_key == "test_api_key_from_env"
        assert connector.client is mock_openai_client
        mock_getenv.assert_called_once_with("XAI_API_KEY")
        mock_openai_class.assert_called_once_with(api_key="test_api_key_from_env", base_url="https://api.x.ai/v1")

    @patch('src.xai_grok_connector.os.getenv')
    @patch('src.xai_grok_connector.OpenAI')
    def test_initialize_success_config_var(self, mock_openai_class, mock_getenv, mock_openai_client):
        """Test successful initialization using config dictionary."""
        mock_getenv.return_value = None # Ensure env var is not used
        mock_openai_class.return_value = mock_openai_client

        connector = XaiGrokConnector()
        config = {'api_key': 'test_api_key_from_config'}
        assert connector.initialize(config) is True
        assert connector.api_key == "test_api_key_from_config"
        assert connector.client is mock_openai_client
        mock_getenv.assert_called_once_with("XAI_API_KEY") # Should still check env var first
        mock_openai_class.assert_called_once_with(api_key="test_api_key_from_config", base_url="https://api.x.ai/v1")

    @patch('src.xai_grok_connector.os.getenv')
    @patch('src.xai_grok_connector.OpenAI')
    def test_initialize_success_config_overrides_env(self, mock_openai_class, mock_getenv, mock_openai_client):
        """Test config API key overrides environment variable."""
        mock_getenv.return_value = "ignored_env_key"
        mock_openai_class.return_value = mock_openai_client

        connector = XaiGrokConnector()
        config = {'api_key': 'test_api_key_from_config'}
        assert connector.initialize(config) is True
        assert connector.api_key == "test_api_key_from_config"
        mock_openai_class.assert_called_once_with(api_key="test_api_key_from_config", base_url="https://api.x.ai/v1")

    @patch('src.xai_grok_connector.os.getenv')
    def test_initialize_failure_no_key(self, mock_getenv, caplog):
        """Test initialization failure when no API key is found."""
        mock_getenv.return_value = None
        connector = XaiGrokConnector()
        config = {}
        assert connector.initialize(config) is False
        assert connector.api_key is None
        assert connector.client is None
        assert "x.ai API key not provided" in caplog.text # Should log error

    @patch('src.xai_grok_connector.os.getenv')
    @patch('src.xai_grok_connector.OpenAI')
    def test_initialize_updates_parameters(self, mock_openai_class, mock_getenv):
        """Test that initialize updates model, temp, max_tokens from config."""
        mock_getenv.return_value = "test_key"
        mock_openai_class.return_value = MagicMock()
        
        connector = XaiGrokConnector(model="old-model", temperature=0.5, max_tokens=1000)
        config = {
            'api_key': 'test_key',
            'model': 'new-model',
            'temperature': 0.9,
            'max_tokens': 2000
        }
        assert connector.initialize(config) is True
        assert connector.model == 'new-model'
        assert connector.temperature == 0.9
        assert connector.max_tokens == 2000

    @patch('src.xai_grok_connector.os.getenv')
    @patch('src.xai_grok_connector.OpenAI')
    def test_initialize_failure_client_exception(self, mock_openai_class, mock_getenv, caplog):
        """Test initialization failure if OpenAI client creation fails."""
        mock_getenv.return_value = "test_key"
        mock_openai_class.side_effect = Exception("Client creation failed")
        
        connector = XaiGrokConnector()
        config = {'api_key': 'test_key'}
        with pytest.raises(XaiGrokConfigurationError, match="Failed to initialize OpenAI client"):
            connector.initialize(config)
        assert connector.client is None # Client should remain None

    # --- Authentication Tests ---
    @patch('src.xai_grok_connector.time.sleep', return_value=None) # Mock sleep to speed up retry tests
    def test_authenticate_success_with_retry(self, mock_sleep, mock_openai_client):
        """Test successful authentication after one retryable error."""
        connector = XaiGrokConnector()
        connector.client = mock_openai_client
        # Simulate a network error on first call, then success
        mock_openai_client.models.list.side_effect = [
            APIConnectionError(request=MagicMock()),
            MagicMock(spec=ModelsPage, data=[MagicMock(spec=Model, id='grok-2-latest')]) # Successful response
        ]
        assert connector.authenticate() is True
        assert mock_openai_client.models.list.call_count == 2
        mock_sleep.assert_called_once()

    def test_authenticate_success(self, mock_openai_client):
        """Test successful authentication."""
        connector = XaiGrokConnector()
        # Simulate successful initialization
        connector.client = mock_openai_client
        assert connector.authenticate() is True
        mock_openai_client.models.list.assert_called_once()

    def test_authenticate_failure_api_error(self, mock_openai_client, caplog):
        """Test authentication failure due to APIError."""
        connector = XaiGrokConnector()
        # Use status code 401 for auth error
        mock_openai_client.models.list.side_effect = APIError("Auth Failed", response=MagicMock(status_code=401), body=None)
        connector.client = mock_openai_client # Must be set after side_effect
        assert connector.authenticate() is False
        assert "Authentication failed (status 401)" in caplog.text # Check log from decorator
        assert "x.ai authentication check failed: Authentication failed (status 401)" in caplog.text # Check log from authenticate method

    def test_authenticate_failure_connection_error(self, mock_openai_client, caplog):
        """Test authentication failure due to APIConnectionError."""
        connector = XaiGrokConnector()
        # Decorator handles retries and raises after exceeding them
        mock_openai_client.models.list.side_effect = APIConnectionError(request=MagicMock())
        assert connector.authenticate() is False
        assert "Network error connecting to x.ai" in caplog.text
        assert "Max retries (3) exceeded" in caplog.text

    def test_authenticate_failure_rate_limit_error(self, mock_openai_client, caplog):
        """Test authentication failure due to RateLimitError."""
        connector = XaiGrokConnector()
        # Decorator handles retries and raises after exceeding them
        mock_openai_client.models.list.side_effect = RateLimitError("Rate limit hit", response=MagicMock(status_code=429), body=None)
        assert connector.authenticate() is False
        assert "Rate limit exceeded" in caplog.text
        assert "Max retries (3) exceeded" in caplog.text

    def test_authenticate_failure_unexpected_error(self, mock_openai_client, caplog):
        """Test authentication failure due to an unexpected error."""
        connector = XaiGrokConnector()
        connector.client = mock_openai_client
        mock_openai_client.models.list.side_effect = Exception("Something broke")
        # Decorator wraps unexpected errors
        with pytest.raises(XaiGrokError, match="Unexpected error during authentication check"):
            connector.authenticate()
        assert "An unexpected error occurred" in caplog.text

    def test_authenticate_failure_not_initialized(self, caplog):
        """Test authentication failure when the client is not initialized."""
        connector = XaiGrokConnector()
        # Decorator should raise config error immediately
        with pytest.raises(XaiGrokConfigurationError, match="client is not initialized"):
            connector.authenticate()

    # --- Send Request Tests ---
    def test_send_request_success(self, mock_openai_client):
        """Test successful request sending."""
        connector = XaiGrokConnector(model="test-model", temperature=0.6, max_tokens=500)
        connector.client = mock_openai_client # Assume initialized
        
        messages = [{"role": "user", "content": "Hello Grok"}]
        expected_params = {
            "model": "test-model",
            "messages": messages,
            "temperature": 0.6,
            "max_tokens": 500,
            "stream": False,
        }
        
        completion_obj = connector.send_request(messages)
        
        mock_openai_client.chat.completions.create.assert_called_once_with(**expected_params)
        # Check if the returned object is the one from the mock
        assert completion_obj is mock_openai_client.chat.completions.create.return_value
        # Assert timeout was passed (or default was used)
        assert mock_openai_client.chat.completions.create.call_args.kwargs['timeout'] == 60 # Default from decorator

    def test_send_request_with_parameters_override(self, mock_openai_client):
        """Test request sending with parameter overrides."""
        connector = XaiGrokConnector(model="default-model", temperature=0.7, max_tokens=1000)
        connector.client = mock_openai_client

        messages = [{"role": "user", "content": "Override test"}]
        override_params = {
            "model": "override-model",
            "temperature": 0.1,
            "max_tokens": 100,
            "stream": False,
            # Default timeout added by decorator
            "timeout": 60
        }
        
        expected_call_params = {
            "model": "override-model",
            "messages": messages,
            "temperature": 0.1,
            "max_tokens": 100,
            "stream": False,
            "timeout": 60
        }

        connector.send_request(messages, parameters=override_params)
        mock_openai_client.chat.completions.create.assert_called_once_with(**expected_call_params)

    def test_send_request_failure_api_error(self, mock_openai_client, caplog):
        """Test request failure due to APIError."""
        connector = XaiGrokConnector()
        connector.client = mock_openai_client
        mock_openai_client.chat.completions.create.side_effect = APIError("API Issue", response=MagicMock(), body=None)
        
        messages = [{"role": "user", "content": "Test - 400 Error"}]
        # Decorator wraps non-retryable API errors
        with pytest.raises(XaiGrokAPIError, match="API error occurred"):
            connector.send_request(messages)
        assert "Non-retryable API error" in caplog.text

    def test_send_request_failure_connection_error(self, mock_openai_client, caplog):
        """Test request failure due to APIConnectionError (should retry)."""
        connector = XaiGrokConnector()
        connector.client = mock_openai_client
        mock_openai_client.chat.completions.create.side_effect = APIConnectionError(request=MagicMock())
        
        messages = [{"role": "user", "content": "Test"}]
        # Decorator should retry and then raise XaiGrokNetworkError
        with pytest.raises(XaiGrokNetworkError, match="Network error connecting to x.ai.*Max retries exceeded"):
            connector.send_request(messages)
        assert mock_openai_client.chat.completions.create.call_count == 4 # Initial + 3 retries

    @patch('src.xai_grok_connector.time.sleep', return_value=None)
    def test_send_request_failure_rate_limit_error(self, mock_sleep, mock_openai_client, caplog):
        """Test request failure due to RateLimitError (should retry)."""
        connector = XaiGrokConnector()
        connector.client = mock_openai_client
        mock_openai_client.chat.completions.create.side_effect = RateLimitError("Rate limit hit", response=MagicMock(status_code=429), body=None)

        messages = [{"role": "user", "content": "Test"}]
        with pytest.raises(XaiGrokRateLimitError, match="Rate limit exceeded.*Max retries exceeded"):
            connector.send_request(messages)
        assert mock_openai_client.chat.completions.create.call_count == 4
        assert mock_sleep.call_count == 3

    @patch('src.xai_grok_connector.time.sleep', return_value=None)
    def test_send_request_failure_server_error_retry(self, mock_sleep, mock_openai_client, caplog):
        """Test request failure due to 500 Server Error (should retry)."""
        connector = XaiGrokConnector()
        connector.client = mock_openai_client
        mock_openai_client.chat.completions.create.side_effect = APIError("Server Down", response=MagicMock(status_code=500), body=None)

        messages = [{"role": "user", "content": "Test"}]
        with pytest.raises(XaiGrokAPIError, match="Server error \(status 500\).*Max retries exceeded"):
            connector.send_request(messages)
        assert mock_openai_client.chat.completions.create.call_count == 4
        assert mock_sleep.call_count == 3

    @patch('src.xai_grok_connector.time.sleep', return_value=None)
    def test_send_request_failure_timeout_retry(self, mock_sleep, mock_openai_client, caplog):
        """Test request failure due to APITimeoutError (should retry)."""
        connector = XaiGrokConnector()
        connector.client = mock_openai_client
        mock_openai_client.chat.completions.create.side_effect = APITimeoutError()

        messages = [{"role": "user", "content": "Test"}]
        with pytest.raises(XaiGrokNetworkError, match="Request timed out.*Max retries exceeded"):
            connector.send_request(messages)
        assert mock_openai_client.chat.completions.create.call_count == 4
        assert mock_sleep.call_count == 3

    @patch('src.xai_grok_connector.time.sleep', return_value=None)
    def test_send_request_success_after_retry(self, mock_sleep, mock_openai_client):
        """Test successful request after one retryable error."""
        connector = XaiGrokConnector()
        connector.client = mock_openai_client

        # Mock successful response data
        mock_usage = MagicMock(spec=CompletionUsage, prompt_tokens=5, completion_tokens=15, total_tokens=20)
        mock_message = MagicMock(spec=ChatCompletionMessage, role='assistant', content='Success after retry')
        mock_choice = MagicMock(spec=Choice, index=0, message=mock_message, finish_reason='stop')
        mock_successful_completion = MagicMock(spec=ChatCompletion, id='chatcmpl-success', model='grok-2-latest', choices=[mock_choice], usage=mock_usage)

        # Simulate one rate limit error, then success
        mock_openai_client.chat.completions.create.side_effect = [
            RateLimitError("Rate limit hit", response=MagicMock(status_code=429), body=None),
            mock_successful_completion
        ]

        messages = [{"role": "user", "content": "Test"}]
        completion_obj = connector.send_request(messages)

        assert mock_openai_client.chat.completions.create.call_count == 2
        assert mock_sleep.call_count == 1
        assert completion_obj.choices[0].message.content == 'Success after retry'

    def test_send_request_failure_unexpected_error(self, mock_openai_client, caplog):
        """Test request failure due to an unexpected error."""
        connector = XaiGrokConnector()
        mock_openai_client.chat.completions.create.side_effect = Exception("Total breakdown")
        
        messages = [{"role": "user", "content": "Test"}]
        # Decorator wraps unexpected errors in XaiGrokError
        with pytest.raises(XaiGrokError, match="An unexpected error occurred during the API call"):
            connector.send_request(messages)
        assert "Unexpected error during API call: Exception" in caplog.text

    def test_send_request_failure_not_initialized(self):
        """Test request failure when the client is not initialized."""
        connector = XaiGrokConnector()
        messages = [{"role": "user", "content": "No Init"}]
        # Decorator should raise config error
        with pytest.raises(XaiGrokConfigurationError, match="client is not initialized"):
            connector.send_request(messages)

    def test_send_request_failure_invalid_messages_none(self):
        """Test sending request with None messages."""
        connector = XaiGrokConnector()
        connector.client = MagicMock() # Needs a client to pass initial check
        
        messages = None
        with pytest.raises(XaiGrokConfigurationError, match="Invalid messages format"):
            connector.send_request(messages)

    def test_send_request_failure_invalid_messages_empty(self):
        """Test sending request with empty list messages."""
        connector = XaiGrokConnector()
        connector.client = MagicMock()
        
        messages = []
        with pytest.raises(XaiGrokConfigurationError, match="Invalid messages format"):
            connector.send_request(messages)

    def test_send_request_failure_invalid_messages_type(self):
        """Test sending request with wrong message type."""
        connector = XaiGrokConnector()
        connector.client = MagicMock()
        
        messages = "not a list"
        with pytest.raises(XaiGrokConfigurationError, match="Invalid messages format"):
            connector.send_request(messages)

    # --- Handle Response Tests ---
    def test_handle_response_success(self, mock_openai_client):
        """Test successful processing of a valid response object."""
        connector = XaiGrokConnector()
        # Use the completion object provided by the fixture
        mock_completion = mock_openai_client.chat.completions.create.return_value 
        
        processed = connector.handle_response(mock_completion)
        
        assert processed["content"] == "Mocked response content"
        assert processed["model"] == "grok-2-latest"
        assert processed["usage"]["prompt_tokens"] == 10
        assert processed["usage"]["completion_tokens"] == 20
        assert processed["usage"]["total_tokens"] == 30 # Make sure usage is extracted correctly
        assert processed["raw_response"] is mock_completion

    def test_handle_response_success_empty_content(self, mock_openai_client):
        """Test successful processing when response content is None."""
        connector = XaiGrokConnector()
        mock_completion = mock_openai_client.chat.completions.create.return_value
        # Modify the mock to have None content
        mock_completion.choices[0].message.content = None
        
        processed = connector.handle_response(mock_completion)
        assert processed["content"] == "" # Should handle empty string content
        assert processed["model"] == "grok-2-latest"
        assert processed["raw_response"] is mock_completion
        
        # Reset mock content for other tests if fixture scope is wider
        mock_completion.choices[0].message.content = 'Mocked response content' 

    def test_handle_response_failure_none_input(self, caplog):
        """Test handle_response failure when input is None."""
        connector = XaiGrokConnector()
        with pytest.raises(XaiGrokResponseError, match="Received None response object"):
            connector.handle_response(None)
        assert "Received None response object" in caplog.text

    def test_handle_response_failure_missing_choices(self, caplog):
        """Test handle_response failure when 'choices' key is missing or response is malformed."""
        connector = XaiGrokConnector()
        malformed_response = MagicMock()
        del malformed_response.choices # Simulate missing attribute
        with pytest.raises(XaiGrokResponseError, match="Unexpected response format"):
            connector.handle_response(malformed_response)
        assert "Failed to process response object structure: AttributeError" in caplog.text

    def test_handle_response_failure_empty_choices(self, caplog):
        """Test handle_response failure when 'choices' list is empty."""
        connector = XaiGrokConnector()
        malformed_response = MagicMock(spec=ChatCompletion)
        malformed_response.choices = [] # Empty list
        with pytest.raises(XaiGrokResponseError, match="Unexpected response format"):
            connector.handle_response(malformed_response)
        assert "Failed to process response object structure: IndexError" in caplog.text

    def test_handle_response_failure_missing_message(self, caplog):
        """Test handle_response failure when choice is missing 'message'."""
        connector = XaiGrokConnector()
        mock_choice = MagicMock(spec=Choice)
        del mock_choice.message # Remove message attribute
        malformed_response = MagicMock(spec=ChatCompletion)
        malformed_response.choices = [mock_choice]
        with pytest.raises(XaiGrokResponseError, match="Unexpected response format"):
            connector.handle_response(malformed_response)
        assert "Failed to process response object structure: AttributeError" in caplog.text

    def test_handle_response_failure_missing_content(self, caplog):
        """Test handle_response failure when message is missing 'content'."""
        connector = XaiGrokConnector()
        mock_message = MagicMock(spec=ChatCompletionMessage)
        del mock_message.content # Remove content attribute
        mock_choice = MagicMock(spec=Choice)
        mock_choice.message = mock_message
        malformed_response = MagicMock(spec=ChatCompletion)
        malformed_response.choices = [mock_choice]
        with pytest.raises(XaiGrokResponseError, match="Unexpected response format"):
            connector.handle_response(malformed_response)
        assert "Failed to process response object structure: AttributeError" in caplog.text

    def test_handle_response_failure_missing_usage(self, caplog):
        """Test handle_response failure when 'usage' key is missing."""
        connector = XaiGrokConnector()
        mock_choice = MagicMock(spec=Choice)
        mock_choice.message = MagicMock(spec=ChatCompletionMessage)
        malformed_response = MagicMock(spec=ChatCompletion)
        malformed_response.choices = [mock_choice]
        del malformed_response.usage # Simulate missing usage
        with pytest.raises(XaiGrokResponseError, match="Unexpected response format"):
            connector.handle_response(malformed_response)
        assert "Failed to process response object structure: AttributeError" in caplog.text

    def test_handle_response_failure_unexpected_exception(self, caplog):
        """Test handle_response catches unexpected exceptions during processing."""
        connector = XaiGrokConnector()
        problematic_response = MagicMock()
        # Mock choices access to raise an unexpected error
        problematic_response.choices.__getitem__.side_effect = Exception("Weird processing error")
        # Should be wrapped in XaiGrokError
        with pytest.raises(XaiGrokError, match="Unexpected error during response handling"):
            connector.handle_response(problematic_response)
        assert "An unexpected error occurred during response handling: Exception - Weird processing error" in caplog.text 