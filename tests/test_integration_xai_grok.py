import pytest
import os
import sys

# Ensure src is importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from src.xai_grok_connector import XaiGrokConnector
from src.exceptions import (
    XaiGrokAuthenticationError,
    XaiGrokAPIError,
    XaiGrokNetworkError,
    XaiGrokResponseError
)

# Environment variable for the API key
API_KEY_ENV_VAR = "XAI_API_KEY"

# Marker for integration tests
integration_test = pytest.mark.skipif(
    not os.getenv(API_KEY_ENV_VAR),
    reason=f"Requires {API_KEY_ENV_VAR} environment variable set for x.ai API key"
)

@pytest.fixture(scope="module")
def real_connector():
    """Provides an initialized real XaiGrokConnector instance for integration tests."""
    api_key = os.getenv(API_KEY_ENV_VAR)
    if not api_key:
        pytest.skip(f"{API_KEY_ENV_VAR} not set, skipping integration tests.")

    connector = XaiGrokConnector()
    initialized = connector.initialize({'api_key': api_key})
    if not initialized:
        pytest.fail("Failed to initialize real connector even though API key was found.")
    
    # Perform a quick authentication check during setup
    try:
        auth_success = connector.authenticate()
        if not auth_success:
             pytest.fail("Real connector failed authentication during setup.")
    except Exception as e:
         pytest.fail(f"Exception during real connector authentication setup: {e}")

    return connector

@integration_test
class TestIntegrationXaiGrokConnector:
    
    def test_integration_authenticate_success(self, real_connector):
        """Test successful authentication against the real API."""
        # The fixture already performs authentication, so if we get here, it worked.
        # We can optionally call it again for explicitness.
        try:
            assert real_connector.authenticate() is True
        except XaiGrokAuthenticationError as e:
             pytest.fail(f"Authentication failed unexpectedly: {e}")

    def test_integration_send_request_success(self, real_connector):
        """Test sending a simple request and getting a valid response."""
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "What is the capital of France? Respond concisely."}
        ]
        try:
            raw_response = real_connector.send_request(messages)
            processed_response = real_connector.handle_response(raw_response)

            assert isinstance(processed_response, dict)
            assert "content" in processed_response
            assert isinstance(processed_response["content"], str)
            assert len(processed_response["content"]) > 0
            assert "paris" in processed_response["content"].lower()
            assert "model" in processed_response
            assert "usage" in processed_response
            assert "prompt_tokens" in processed_response["usage"]
            assert "raw_response" in processed_response

        except (XaiGrokAPIError, XaiGrokNetworkError, XaiGrokResponseError) as e:
            pytest.fail(f"API call failed unexpectedly during simple request test: {e}")
        except Exception as e:
             pytest.fail(f"An unexpected non-API error occurred: {e}")

    # Optional: Test with a known invalid key if you have one and expect AuthenticationError
    # def test_integration_invalid_auth(self):
    #     connector = XaiGrokConnector()
    #     initialized = connector.initialize({'api_key': 'invalid-key-string'})
    #     assert initialized # Initialization might succeed
    #     with pytest.raises(XaiGrokAuthenticationError):
    #         connector.authenticate()

    # Note: Testing rate limits precisely is difficult and unreliable in integration tests.
    # It's better suited for staging environments or specific load tests. 