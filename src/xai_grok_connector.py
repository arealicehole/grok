import os
import logging
import time
import functools
import asyncio
from typing import Dict, Any, Optional, List, Callable, Type
from openai import OpenAI, APIError, APIConnectionError, RateLimitError, AuthenticationError, APITimeoutError
from openai import AsyncOpenAI
from .llm_connector import LLM_Connector
from .exceptions import (
    XaiGrokError,
    XaiGrokConfigurationError,
    XaiGrokAuthenticationError,
    XaiGrokAPIError,
    XaiGrokNetworkError,
    XaiGrokRateLimitError,
    XaiGrokResponseError,
)

# Configure logging
# Consider moving this to a central config if not already done
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

DEFAULT_RETRY_ATTEMPTS = 3
DEFAULT_RETRY_DELAY = 1  # seconds
DEFAULT_API_TIMEOUT = 60 # seconds

def retry_api_call(max_retries: int = DEFAULT_RETRY_ATTEMPTS, initial_delay: float = DEFAULT_RETRY_DELAY, timeout: float = DEFAULT_API_TIMEOUT):
    """
    Decorator to handle retries and exception wrapping for x.ai API calls.

    Args:
        max_retries: Maximum number of retry attempts.
        initial_delay: Initial delay between retries in seconds.
        timeout: Request timeout in seconds passed to the underlying API call.

    Raises:
        XaiGrokConfigurationError: If the connector's client is not initialized.
        XaiGrokRateLimitError: If a rate limit error (429) persists after retries.
        XaiGrokNetworkError: If a network connection or timeout error persists after retries.
        XaiGrokAPIError: If a retryable server error (5xx) persists after retries,
                         or if a non-retryable client error (4xx, excluding 401/403/429) occurs.
        XaiGrokAuthenticationError: If an authentication error (401/403) occurs.
        XaiGrokError: For any other unexpected errors during the API call or retry process.
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            connector_instance = args[0] # Assumes the first arg is 'self'
            if not connector_instance.client:
                 # Ensure client is initialized before attempting call
                 raise XaiGrokConfigurationError("XaiGrokConnector client is not initialized. Call initialize() first.")

            current_delay = initial_delay
            for attempt in range(max_retries + 1): # +1 for the initial attempt
                try:
                    # Pass the timeout to the underlying function if it accepts it
                    # This requires the decorated function to handle the timeout param
                    if 'timeout' in func.__code__.co_varnames:
                         kwargs['timeout'] = timeout
                    elif 'request_params' in kwargs and isinstance(kwargs['request_params'], dict):
                         kwargs['request_params']['timeout'] = timeout # Handle cases like send_request
                    else:
                         # If timeout cannot be passed, log a warning or handle differently
                         logger.debug("Timeout parameter not directly applicable to decorated function signature, relying on client default.")

                    # Execute the decorated function (e.g., client.models.list(), client.chat.completions.create())
                    result = await func(*args, **kwargs)
                    return result # Success

                except RateLimitError as e:
                    error_type = XaiGrokRateLimitError
                    error_message = f"Rate limit exceeded (attempt {attempt + 1}/{max_retries + 1})"
                    original_exception = e
                except APIConnectionError as e:
                    error_type = XaiGrokNetworkError
                    error_message = f"Network error connecting to x.ai (attempt {attempt + 1}/{max_retries + 1})"
                    original_exception = e
                except APITimeoutError as e:
                    error_type = XaiGrokNetworkError
                    error_message = f"Request timed out after {timeout}s (attempt {attempt + 1}/{max_retries + 1})"
                    original_exception = e
                except APIError as e:
                    # Check for retryable server errors (e.g., 5xx)
                    if e.status_code and 500 <= e.status_code < 600:
                        error_type = XaiGrokAPIError
                        error_message = f"Server error (status {e.status_code}) received from x.ai (attempt {attempt + 1}/{max_retries + 1})"
                        original_exception = e
                    else:
                        # Non-retryable API error (e.g., 4xx client errors, excluding 429 handled above)
                        logger.error(f"Non-retryable API error: {type(e).__name__} - Status: {e.status_code} - {e}", exc_info=False)
                        if e.status_code == 401 or e.status_code == 403:
                            raise XaiGrokAuthenticationError(message=f"Authentication failed (status {e.status_code})", status_code=e.status_code, original_exception=e)
                        else:
                            raise XaiGrokAPIError(message=f"API error occurred (status {e.status_code})", status_code=e.status_code, original_exception=e)
                except AuthenticationError as e: # Catch direct AuthenticationError if openai lib raises it separately
                     logger.error(f"Authentication error: {e}", exc_info=False)
                     raise XaiGrokAuthenticationError(original_exception=e)
                except Exception as e:
                    # Catch any other unexpected errors during the API call
                    logger.error(f"Unexpected error during API call: {type(e).__name__} - {e}", exc_info=True)
                    raise XaiGrokError(message="An unexpected error occurred during the API call", original_exception=e)

                # If it's a retryable error and we haven't exceeded retries
                if attempt < max_retries:
                    logger.warning(f"{error_message}. Retrying in {current_delay:.2f} seconds...")
                    await asyncio.sleep(current_delay)
                    current_delay *= 2 # Exponential backoff
                else:
                    logger.error(f"{error_message}. Max retries ({max_retries}) exceeded.")
                    raise error_type(message=f"{error_message}. Max retries exceeded.", original_exception=original_exception) from e

        return wrapper
    return decorator

class XaiGrokConnector(LLM_Connector):
    """Connector for interacting with the x.ai Grok API using OpenAI compatibility."""

    def __init__(self, model: str = "grok-2-latest", temperature: float = 0.7, max_tokens: int = 8192):
        """
        Initializes basic parameters. Call initialize() to finalize setup.
        """
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.api_key: Optional[str] = None
        self.client: Optional[AsyncOpenAI] = None
        logger.info("XaiGrokConnector partially initialized. Call initialize() to complete setup.")

    def initialize(self, config: Dict[str, Any]) -> bool:
        """
        Initialize the connector with configuration parameters.

        Args:
            config: Dictionary containing configuration parameters.
                    Expected keys: 'api_key' (optional, reads from XAI_API_KEY env if missing),
                                   'model' (optional), 'temperature' (optional), 'max_tokens' (optional).

        Returns:
            bool: True if initialization was successful (API key found), False otherwise.

        Raises:
            XaiGrokConfigurationError: If the OpenAI client fails to initialize (e.g., due to underlying issues).
        """
        self.api_key = config.get('api_key') or os.getenv("XAI_API_KEY")
        if not self.api_key:
            logger.error("x.ai API key not provided in config or found in environment variable XAI_API_KEY")
            return False

        try:
            self.client = AsyncOpenAI(
                api_key=self.api_key,
                base_url="https://api.x.ai/v1",
            )
            # Update parameters after client is created, potentially verifying against available models later
            self.model = config.get('model', self.model)
            self.temperature = config.get('temperature', self.temperature)
            self.max_tokens = config.get('max_tokens', self.max_tokens)
            logger.info(f"XaiGrokConnector initialized successfully for model: {self.model}")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize OpenAI client for x.ai: {e}", exc_info=True)
            self.client = None
            # Raise configuration error if client init fails fundamentally
            raise XaiGrokConfigurationError(message="Failed to initialize OpenAI client", original_exception=e)
            return False

    @retry_api_call() # Use default retry settings
    async def authenticate(self) -> bool:
        """
        Authenticates by trying a simple API call (listing models).
        Uses the @retry_api_call decorator to handle retries for transient errors.

        Returns:
            bool: True if authentication seems successful, False otherwise.

        Raises:
            XaiGrokConfigurationError: If the client is not initialized before calling.
            XaiGrokError: For unexpected errors not handled by the retry decorator directly
                          (though most API/network errors result in returning False after retries).
        """
        if not self.client:
            logger.warning("Authentication check failed: Client not initialized.")
            return False
        try:
            # Simple call to verify API key and connection
            await self.client.models.list()
            logger.info("x.ai authentication check successful.")
            return True
        except (XaiGrokAuthenticationError, XaiGrokNetworkError, XaiGrokAPIError, XaiGrokRateLimitError) as e:
            # Exceptions are already logged by the decorator, just return False
            logger.error(f"x.ai authentication check failed: {e}")
            return False
        except Exception as e:
            logger.error(f"An unexpected error occurred during x.ai authentication check: {e}", exc_info=True)
            # Wrap unexpected errors
            raise XaiGrokError(message="Unexpected error during authentication check", original_exception=e)
            return False

    @retry_api_call() # Use default retry settings
    async def send_request(self, messages: List[Dict[str, str]], parameters: Optional[Dict[str, Any]] = None) -> Any:
        """
        Sends a request to the Grok chat completion endpoint.
        Uses the @retry_api_call decorator to handle retries and specific API errors.
        Note: The return type is Any because it directly returns the OpenAI completion object.
              The consuming code should use `handle_response` to process this object.

        Args:
            messages: A list of message dictionaries, e.g., [{'role': 'user', 'content': 'Hello'}]
            parameters: Optional parameters to override defaults (temperature, max_tokens, model, timeout).

        Returns:
            Any: The raw completion object from the OpenAI client.

        Raises:
            XaiGrokConfigurationError: If the client is not initialized or messages format is invalid.
            XaiGrokRateLimitError: If rate limits persist after retries.
            XaiGrokNetworkError: If network/timeout errors persist after retries.
            XaiGrokAPIError: If non-retryable API errors occur or retryable ones persist.
            XaiGrokAuthenticationError: If authentication fails (401/403).
            XaiGrokError: For other unexpected errors during the API call itself (before decorator handling).
        """
        if not self.client:
            raise ValueError("XaiGrokConnector client is not initialized. Call initialize() first.")
        if not messages or not isinstance(messages, list):
            # Use specific configuration error for invalid input
            raise XaiGrokConfigurationError("Invalid messages format. Expected a list of dictionaries.")

        request_params = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "stream": False,
        }

        # Apply overrides from parameters, converting known keys if needed
        if parameters:
            # Ensure timeout isn't passed directly if handled by decorator
            param_overrides = {k: v for k, v in parameters.items() if k != 'timeout'} 
            request_params.update(param_overrides)

        logger.debug(f"Sending request to Grok model {request_params['model']} with {len(messages)} messages.")
        try:
            completion = await self.client.chat.completions.create(**request_params)
            logger.debug("Received completion object from x.ai.")
            # The interface asks for a request ID string, but chat completions return an object.
            # Returning the whole object for handle_response to process.
            return completion
        except Exception as e:
            logger.error(f"Unexpected error during chat completion: {e}", exc_info=True)
            raise ConnectionError(f"Failed to send request to x.ai: {e}")

    def handle_response(self, response: Any) -> Dict[str, Any]:
        """
        Processes the raw completion object from send_request.

        Args:
            response: The raw completion object from openai.chat.completions.create.

        Returns:
            Dict[str, Any]: A dictionary containing extracted 'content', 'model', 'usage',
                           and the 'raw_response' object itself.

        Raises:
            XaiGrokResponseError: If the response is None or its structure is invalid/unexpected.
            XaiGrokError: For other unexpected errors during processing.
        """
        # Add check if response is None or fundamentally broken before processing
        if response is None:
             logger.error("Received None response object to handle.")
             raise XaiGrokResponseError("Received None response object")

        try:
            content = response.choices[0].message.content
            model_used = response.model
            usage = response.usage

            processed_response = {
                "content": content or "",
                "model": model_used,
                "usage": {
                    "prompt_tokens": usage.prompt_tokens,
                    "completion_tokens": usage.completion_tokens,
                    "total_tokens": usage.total_tokens,
                },
                "raw_response": response # Include the original object
            }
            logger.debug("Successfully processed response content.")
            return processed_response
        except (AttributeError, IndexError, TypeError, KeyError) as e:
            logger.error(f"Failed to process response object structure: {type(e).__name__} - {e}. Response: {response}", exc_info=False)
            raise XaiGrokResponseError(message=f"Unexpected response format from x.ai API: {e}", original_exception=e)
        except Exception as e:
             logger.error(f"An unexpected error occurred during response handling: {e}", exc_info=True)
             raise XaiGrokError(message="Unexpected error during response handling", original_exception=e)

    async def analyze_profile(self, profile_id: str, profile_data: Dict[str, Any], prompt_template: str = "Analyze the following profile data: {data}") -> Dict[str, Any]:
        """
        Analyzes a single profile by sending its data to the XaiGrok API.

        Args:
            profile_id: The unique identifier for the profile.
            profile_data: A dictionary containing the profile data to be analyzed.
            prompt_template: A string template for the prompt. {data} will be replaced by profile_data.


        Returns:
            A dictionary containing the profileId, analysis data (or error), and status.
        """
        if not self.client:
            logger.error(f"Cannot analyze profile {profile_id}: XaiGrokConnector client is not initialized.")
            return {"profileId": profile_id, "error": XaiGrokConfigurationError("Client not initialized"), "status": "error"}

        try:
            # Simple prompt, can be made more sophisticated
            # For now, just sending the profile_data as a string. Consider how to format complex data.
            content_message = prompt_template.format(data=str(profile_data))
            
            messages = [{"role": "user", "content": content_message}]
            
            logger.info(f"Sending profile {profile_id} for analysis.")
            raw_completion = await self.send_request(messages=messages)
            
            if raw_completion:
                processed_response = self.handle_response(raw_completion)
                logger.info(f"Successfully analyzed profile {profile_id}.")
                return {"profileId": profile_id, "data": processed_response, "status": "success"}
            else:
                # This case should ideally be handled by send_request raising an error
                logger.error(f"Received no completion for profile {profile_id} from send_request.")
                return {"profileId": profile_id, "error": XaiGrokResponseError("No completion data received"), "status": "error"}

        except XaiGrokError as e: # Catch our specific errors
            logger.error(f"XaiGrok specific error analyzing profile {profile_id}: {e}", exc_info=False)
            return {"profileId": profile_id, "error": e, "status": "error"}
        except Exception as e:
            logger.error(f"Unexpected error analyzing profile {profile_id}: {e}", exc_info=True)
            return {"profileId": profile_id, "error": XaiGrokError(message="Unexpected error during profile analysis", original_exception=e), "status": "error"}

    async def analyze_multiple_profiles(self, profiles: List[Dict[str, Any]], prompt_template: str = "Analyze the following profile data: {data}") -> List[Dict[str, Any]]:
        """
        Analyzes multiple profiles concurrently using asyncio.gather.

        Args:
            profiles: A list of dictionaries, where each dictionary should have
                      at least 'id' (profile_id) and 'data' (profile_data).
            prompt_template: A string template for the prompt. {data} will be replaced by profile_data.


        Returns:
            A list of dictionaries, each corresponding to the result of an analysis attempt.
            Each dictionary will have 'profileId', 'status', and either 'data' or 'error'.
        """
        if not self.client:
            logger.error("Cannot analyze multiple profiles: XaiGrokConnector client is not initialized.")
            # Return error status for all profiles if client isn't ready
            return [
                {"profileId": profile.get('id', f"unknown_profile_{i}"), "error": XaiGrokConfigurationError("Client not initialized"), "status": "error"}
                for i, profile in enumerate(profiles)
            ]

        if not profiles:
            return []

        tasks = []
        for profile in profiles:
            profile_id = profile.get('id')
            profile_data = profile.get('data')
            if profile_id is None or profile_data is None:
                logger.warning(f"Skipping profile due to missing 'id' or 'data': {profile}")
                # Or append an error result directly for this malformed profile entry
                # For now, just skipping. Consider how to report this.
                continue
            tasks.append(self.analyze_profile(profile_id, profile_data, prompt_template=prompt_template))

        logger.info(f"Starting concurrent analysis for {len(tasks)} profiles.")
        # return_exceptions=True allows us to get all results, even if some tasks raise exceptions
        results = await asyncio.gather(*tasks, return_exceptions=True)
        logger.info(f"Finished concurrent analysis for {len(tasks)} profiles.")

        processed_results = []
        for i, result_or_exception in enumerate(results):
            # Assuming tasks list and results list correspond by index
            # This might be fragile if profiles were skipped when creating tasks.
            # A more robust way would be to map original profile_id to results.
            # For now, relying on the order. The skipped profiles won't be in `tasks` or `results`.
            
            # Find the original profile_id corresponding to this result.
            # This is a bit inefficient but necessary if tasks were skipped.
            # A better approach would be to include profile_id in the task itself or map before gather.
            # For simplicity, if the result is a dictionary and has profileId, use it.
            # Otherwise, try to get it from the original profiles list if the order is maintained.

            if isinstance(result_or_exception, Exception):
                # If asyncio.gather caught an exception raised by analyze_profile that wasn't already packaged
                # This typically means an unhandled error within analyze_profile *before* it returns its dict.
                # analyze_profile is designed to catch its own errors and return a dict.
                # However, if something unexpected happened (e.g. in asyncio itself, or a bug in analyze_profile's try/except)
                profile_id_for_error = "unknown_profile" # Fallback
                # Try to find the profile_id based on the index if possible, assuming tasks list order matches profiles list order
                # This is tricky if profiles were skipped.
                # For now, we'll use a generic ID or improve this if necessary.
                # Let's assume analyze_profile always returns a dict, even for errors it catches.
                # So this branch might be less common for XaiGrokError, but good for other unexpected exceptions.
                
                # Try to get profile_id from the input list (if order was maintained)
                # This requires careful indexing if any profiles were skipped during task creation
                original_profile_index = i # This assumes no skipping, which might be wrong.
                                        # A better approach for a robust solution:
                                        # Create a mapping of task to profile_id before asyncio.gather
                                        # or ensure analyze_profile always returns a dict with profileId.
                                        # For now, the current analyze_profile *does* return a dict.

                logger.error(f"Unhandled exception during concurrent analysis for a profile (index {i}): {result_or_exception}", exc_info=isinstance(result_or_exception, Exception))
                processed_results.append({
                    "profileId": f"profile_at_index_{i}", # Fallback, improve if needed
                    "error": XaiGrokError(message="Unhandled exception in gather", original_exception=result_or_exception),
                    "status": "error"
                })
            elif isinstance(result_or_exception, dict) and 'profileId' in result_or_exception:
                 # This is the expected case, where analyze_profile returned a dict
                processed_results.append(result_or_exception)
            else:
                # Unexpected result type from asyncio.gather
                logger.error(f"Unexpected result type from asyncio.gather for a profile (index {i}): {result_or_exception}")
                processed_results.append({
                    "profileId": f"profile_at_index_{i}", # Fallback
                    "error": XaiGrokError(message=f"Unexpected result type: {type(result_or_exception)}"),
                    "status": "error"
                })
        return processed_results 