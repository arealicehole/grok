import unittest
from unittest.mock import MagicMock, patch
from src.llm_connector import LLM_Connector
from typing import Dict, Any, Optional

class MockConnector(LLM_Connector):
    """Mock implementation of LLM_Connector for testing."""

    def initialize(self, config: Dict[str, Any]) -> bool:
        self.config = config
        # Simulate success
        return True

    def authenticate(self) -> bool:
        # Simulate authentication based on presence of a key, for example
        return self.config is not None and 'api_key' in self.config

    def send_request(self, prompt: str, parameters: Optional[Dict[str, Any]] = None) -> str:
        # Simulate sending request and returning an ID
        return "mock-request-id-123"

    def handle_response(self, response: Any) -> Dict[str, Any]:
        # Simulate handling a response and returning structured data
        return {"text": "This is a mock response", "metadata": {"raw_response": response}}

class TestLLMConnectorInterface(unittest.TestCase):

    def setUp(self):
        """Set up a mock connector instance before each test."""
        self.connector = MockConnector()
        self.test_config = {"api_key": "test_key_123", "endpoint": "http://mock.endpoint"}

    def test_interface_methods_exist(self):
        """Test that all abstract methods are implemented in the mock."""
        # Initialization check
        self.assertTrue(hasattr(self.connector, 'initialize'))
        self.assertTrue(callable(self.connector.initialize))

        # Authentication check
        self.assertTrue(hasattr(self.connector, 'authenticate'))
        self.assertTrue(callable(self.connector.authenticate))

        # Send request check
        self.assertTrue(hasattr(self.connector, 'send_request'))
        self.assertTrue(callable(self.connector.send_request))

        # Handle response check
        self.assertTrue(hasattr(self.connector, 'handle_response'))
        self.assertTrue(callable(self.connector.handle_response))

    def test_mock_initialization_success(self):
        """Test successful initialization of the mock connector."""
        self.assertTrue(self.connector.initialize(self.test_config))
        self.assertEqual(self.connector.config, self.test_config)

    def test_mock_authentication_success(self):
        """Test successful authentication with valid config."""
        self.connector.initialize(self.test_config)
        self.assertTrue(self.connector.authenticate())

    def test_mock_authentication_failure(self):
        """Test authentication failure with invalid config."""
        invalid_config = {"endpoint": "http://mock.endpoint"} # Missing api_key
        self.connector.initialize(invalid_config)
        self.assertFalse(self.connector.authenticate())

    def test_mock_send_request(self):
        """Test the send_request method of the mock connector."""
        request_id = self.connector.send_request("Test prompt")
        self.assertEqual(request_id, "mock-request-id-123")

    def test_mock_handle_response(self):
        """Test the handle_response method of the mock connector."""
        raw_response = {"data": "some raw data"}
        processed_response = self.connector.handle_response(raw_response)
        self.assertIsInstance(processed_response, dict)
        self.assertIn("text", processed_response)
        self.assertIn("metadata", processed_response)
        self.assertEqual(processed_response["metadata"]["raw_response"], raw_response)

if __name__ == '__main__':
    unittest.main() 