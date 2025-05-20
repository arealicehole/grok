import logging
import time
import requests
import random # Moved import for jitter in retry logic
from typing import Dict, Any, Optional

from .base_connector import BaseLLMConnector
from .exceptions import (
    APIError, AuthenticationError, AuthorizationError, InvalidRequestError,
    RateLimitError, APIServerError, APIConnectionError, APITimeoutError
)
# Assuming config.py is in the parent directory (src/)
# If src/connectors/ is a package, this might need adjustment
from .. import config 

# Configure logging
logger = logging.getLogger(__name__)
# Basic logging configuration, can be enhanced in main application setup
logging.basicConfig(level=config.LOG_LEVEL)

# Default retry parameters (can be overridden in __init__)
DEFAULT_MAX_RETRIES = 3
DEFAULT_INITIAL_BACKOFF_SECONDS = 1.0
DEFAULT_MAX_BACKOFF_SECONDS = 60.0
DEFAULT_BACKOFF_FACTOR = 2.0

class XaiGrokConnector(BaseLLMConnector):
    """
    Connector for the Xai Grok API.
    Handles request formatting, API communication, error handling, and retries.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_endpoint: Optional[str] = None,
        default_model: Optional[str] = None,
        timeout: Optional[int] = None,
        max_retries: Optional[int] = None,
        initial_backoff_seconds: float = DEFAULT_INITIAL_BACKOFF_SECONDS,
        max_backoff_seconds: float = DEFAULT_MAX_BACKOFF_SECONDS,
        backoff_factor: float = DEFAULT_BACKOFF_FACTOR
    ):
        """
        Initialize the XaiGrokConnector.

        Args:
            api_key (Optional[str]): Xai API key. Defaults to config.XAI_API_KEY.
            api_endpoint (Optional[str]): API endpoint URL. Defaults to config.XAI_API_ENDPOINT.
            default_model (Optional[str]): Default model to use. Defaults to config.DEFAULT_GROK_MODEL.
            timeout (Optional[int]): Request timeout in seconds. Defaults to config.REQUEST_TIMEOUT_SECONDS.
            max_retries (Optional[int]): Maximum number of retries for transient errors. Defaults to config.MAX_RETRIES.
            initial_backoff_seconds (float): Initial backoff time in seconds.
            max_backoff_seconds (float): Maximum backoff time in seconds.
            backoff_factor (float): Factor by which to increase backoff time.
        """
        self.api_key = api_key or config.XAI_API_KEY
        self.api_endpoint = api_endpoint or config.XAI_API_ENDPOINT
        self.default_model = default_model or config.DEFAULT_GROK_MODEL
        self.timeout = timeout or config.REQUEST_TIMEOUT_SECONDS
        self.max_retries = max_retries or config.MAX_RETRIES
        self.initial_backoff_seconds = initial_backoff_seconds
        self.max_backoff_seconds = max_backoff_seconds
        self.backoff_factor = backoff_factor

        if not self.api_key:
            logger.error("XAI_API_KEY is not configured. Connector will not be able to authenticate.")
            # Potentially raise an error here if API key is strictly required at init
            # raise ValueError("XAI_API_KEY must be provided or set in environment.")

        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        })
        logger.info(f"XaiGrokConnector initialized for endpoint: {self.api_endpoint}, model: {self.default_model}")

    def _prepare_request_payload(
        self,
        transcript_text: str,
        profile_instructions: str,
        model: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Prepares the JSON payload for the Xai Grok API call."""
        if not transcript_text:
            logger.error("Transcript text cannot be empty for API request.")
            raise InvalidRequestError("Transcript text cannot be empty.")

        # Grok API expects messages in a specific format
        messages = [
            {"role": "system", "content": profile_instructions},
            {"role": "user", "content": transcript_text}
        ]

        payload = {
            "model": model or self.default_model,
            "messages": messages,
            # Common default parameters, can be overridden by kwargs
            "temperature": kwargs.get("temperature", 0.7),
            "max_tokens": kwargs.get("max_tokens", 2048), # Adjust as needed for Grok
            "top_p": kwargs.get("top_p", 1.0),
            # Add other Grok specific parameters if necessary
        }
        
        # Merge any other explicit kwargs, overriding defaults
        # Be careful not to overwrite essential fields like 'model' or 'messages' unless intended
        for key, value in kwargs.items():
            if key not in ["temperature", "max_tokens", "top_p"]:
                payload[key] = value

        logger.debug(f"Prepared XAI Grok API request payload: {payload}") # Be mindful of logging sensitive data
        return payload

    def send_analysis_request(
        self,
        transcript_text: str,
        profile_instructions: str,
        model: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Sends an analysis request to the Xai Grok API with retry logic."""
        if not self.api_key:
            raise AuthenticationError("API key not configured. Cannot send request.")

        payload = self._prepare_request_payload(
            transcript_text, profile_instructions, model, **kwargs
        )

        current_backoff = self.initial_backoff_seconds
        last_exception = None

        for attempt in range(self.max_retries + 1):
            try:
                logger.info(f"Sending request to XAI Grok API (Attempt {attempt + 1}/{self.max_retries + 1})")
                response = self.session.post(
                    self.api_endpoint,
                    json=payload,
                    timeout=self.timeout
                )
                response.raise_for_status() # Raises HTTPError for bad responses (4xx or 5xx)
                
                logger.info(f"Received successful response from XAI Grok API (Status: {response.status_code})")
                return response.json()

            except requests.exceptions.Timeout as e:
                logger.warning(f"Request timed out (Attempt {attempt + 1}): {e}")
                last_exception = APITimeoutError(f"Request timed out after {self.timeout}s", details=str(e))
            except requests.exceptions.ConnectionError as e:
                logger.warning(f"Connection error (Attempt {attempt + 1}): {e}")
                last_exception = APIConnectionError(f"Failed to connect to API: {self.api_endpoint}", details=str(e))
            except requests.exceptions.HTTPError as e:
                status_code = e.response.status_code
                error_content = e.response.text
                logger.error(f"HTTP error (Status: {status_code}, Attempt {attempt + 1}): {e}. Response: {error_content}")
                
                if status_code == 401:
                    last_exception = AuthenticationError("Authentication failed. Check API key.", details=error_content)
                    break # No point in retrying auth errors
                elif status_code == 403:
                    last_exception = AuthorizationError("Authorization failed. Insufficient permissions.", details=error_content)
                    break # No point in retrying authz errors
                elif status_code == 400:
                    last_exception = InvalidRequestError("Invalid request. Check payload.", details=error_content)
                    break # No point in retrying bad requests
                elif status_code == 429:
                    retry_after_str = e.response.headers.get("Retry-After")
                    retry_after_seconds = int(retry_after_str) if retry_after_str and retry_after_str.isdigit() else (2 ** attempt) + 1
                    logger.warning(f"Rate limit hit. Retrying after {retry_after_seconds} seconds.")
                    last_exception = RateLimitError("Rate limit exceeded", details=error_content, retry_after=retry_after_seconds)
                    if attempt < self.max_retries: # only sleep if we are going to retry
                        time.sleep(retry_after_seconds)
                    continue # Explicitly continue to retry for rate limit
                elif 500 <= status_code < 600:
                    last_exception = APIServerError(f"API server error (Status: {status_code})", status_code=status_code, details=error_content)
                    # Retry server errors
                else:
                    last_exception = APIError(f"Unhandled HTTP error (Status: {status_code})", status_code=status_code, details=error_content)
                    break # Don't retry unknown client errors by default
            
            except Exception as e:
                logger.exception(f"An unexpected error occurred during API request (Attempt {attempt + 1}): {e}")
                last_exception = APIError(f"An unexpected error occurred: {str(e)}", details=str(e))
                break # Stop on truly unexpected errors

            if attempt < self.max_retries:
                sleep_duration = (2 ** attempt) + (random.uniform(0, 1) if status_code not in [429] else 0) # Jitter, but not for 429 handled above
                logger.info(f"Retrying in {sleep_duration:.2f} seconds...")
                time.sleep(sleep_duration)
        
        logger.error(f"Failed to send request to XAI Grok API after {self.max_retries + 1} attempts.")
        if last_exception:
            raise last_exception
        else:
            # This case should ideally not be reached if retries are exhausted
            raise APIError("Failed to send request after all retries, but no specific exception was captured.")

    # Helper methods (could be part of the class or standalone utility functions)
    def _log_request_details(self, method: str, url: str, payload: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, str]] = None):
        # Enhanced logging for requests, redacting sensitive info like API keys from headers/payload if necessary
        # For now, a simple log
        logger.debug(f"Sending {method} request to {url}. Payload: {payload}. Headers: {headers}")

    def _log_response_details(self, response: requests.Response):
        # Enhanced logging for responses
        logger.debug(f"Received response: Status {response.status_code}. Headers: {response.headers}. Content: {response.text[:500]}...")

# Example Usage (for testing or direct use):
if __name__ == '__main__':
    # This requires XAI_API_KEY to be set in the environment
    if not config.XAI_API_KEY:
        print("Please set the XAI_API_KEY environment variable to run this example.")
    else:
        connector = XaiGrokConnector()
        sample_transcript = "This is a test transcript about AI and LLMs."
        sample_instructions = "Analyze the sentiment of the transcript and identify key topics."
        try:
            print(f"Sending request with model: {connector.default_model}")
            response_data = connector.send_analysis_request(sample_transcript, sample_instructions)
            print("\nAPI Response:")
            import json
            print(json.dumps(response_data, indent=2))
        except APIError as e:
            print(f"\nError during API call: {e}")
            if hasattr(e, 'details') and e.details:
                print(f"Details: {e.details}") 