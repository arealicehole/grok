from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

class BaseLLMConnector(ABC):
    """
    Abstract Base Class for Large Language Model connectors.
    Defines a common interface for interacting with different LLM APIs.
    """

    @abstractmethod
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the connector with necessary configuration.
        Config might include API keys, endpoints, default model parameters, etc.
        """
        pass

    @abstractmethod
    def send_analysis_request(
        self,
        transcript_text: str,
        profile_instructions: str,
        model: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Sends an analysis request to the LLM.

        Args:
            transcript_text (str): The main text to be analyzed.
            profile_instructions (str): System-level instructions or context for the analysis.
            model (Optional[str]): The specific model to use for this request.
                                   If None, a default model for the connector should be used.
            **kwargs: Additional parameters specific to the LLM API (e.g., temperature, max_tokens).

        Returns:
            Dict[str, Any]: The JSON response from the LLM API, parsed into a dictionary.

        Raises:
            AuthenticationError: If API authentication fails.
            APIError: For other API-related errors (e.g., rate limits, server errors).
            ConnectionError: For network-related issues.
            InvalidRequestError: If the request payload is malformed or invalid.
        """
        pass

    # Potentially add other common methods like:
    # @abstractmethod
    # def list_available_models(self) -> List[str]:
    #     pass

    # @abstractmethod
    # def get_model_capabilities(self, model_name: str) -> Dict[str, Any]:
    #     pass 