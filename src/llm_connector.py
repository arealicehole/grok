from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

class LLM_Connector(ABC):
    """Base interface for LLM service connectors."""

    @abstractmethod
    def initialize(self, config: Dict[str, Any]) -> bool:
        """
        Initialize the connector with configuration parameters.

        Args:
            config: Dictionary containing configuration parameters like API keys,
                   endpoints, model parameters, etc.

        Returns:
            bool: True if initialization was successful, False otherwise

        Raises:
            ValueError: If required configuration parameters are missing
        """
        pass

    @abstractmethod
    def authenticate(self) -> bool:
        """
        Authenticate with the LLM service.

        Returns:
            bool: True if authentication was successful, False otherwise

        Raises:
            ConnectionError: If unable to connect to the service
            AuthenticationError: If authentication fails
        """
        pass

    @abstractmethod
    def send_request(self, prompt: str, parameters: Optional[Dict[str, Any]] = None) -> str:
        """
        Send a request to the LLM service.

        Args:
            prompt: The text prompt to send to the LLM
            parameters: Optional parameters to customize the request (temperature, max_tokens, etc.)

        Returns:
            str: Request ID or other identifier for tracking

        Raises:
            ConnectionError: If unable to connect to the service
            RequestError: If the request is malformed or rejected
        """
        pass

    @abstractmethod
    def handle_response(self, response: Any) -> Dict[str, Any]:
        """
        Process the response from the LLM service.

        Args:
            response: The raw response from the LLM service

        Returns:
            Dict[str, Any]: Processed response with standardized format

        Raises:
            ResponseError: If the response cannot be processed
        """
        pass 