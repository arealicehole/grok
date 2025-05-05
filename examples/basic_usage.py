import os
import sys
import logging

# Ensure src is importable by adding the parent directory (project root) to the path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.insert(0, project_root)

from src.xai_grok_connector import XaiGrokConnector
from src.exceptions import (
    XaiGrokError,
    XaiGrokConfigurationError,
    XaiGrokAuthenticationError
)

# Configure logging for the example
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("basic_usage_example")

def main():
    logger.info("Starting XaiGrokConnector basic usage example...")

    # --- Configuration ---
    # The connector will automatically look for XAI_API_KEY environment variable
    # You can override it here if needed:
    # config = {'api_key': 'YOUR_XAI_API_KEY_HERE'}
    config = {}

    # --- Initialization ---
    connector = XaiGrokConnector()
    try:
        if not connector.initialize(config):
            logger.error("Connector initialization failed. Check API key (XAI_API_KEY env var) or config.")
            return
        logger.info("Connector initialized successfully.")
    except XaiGrokConfigurationError as e:
         logger.error(f"Configuration error during initialization: {e}")
         return
    except Exception as e:
         logger.error(f"Unexpected error during initialization: {e}", exc_info=True)
         return

    # --- Authentication (Optional but Recommended) ---
    # The @retry_api_call decorator handles retries within authenticate()
    try:
        logger.info("Attempting authentication...")
        if connector.authenticate():
            logger.info("Authentication successful.")
        else:
            # Authentication failure after retries is usually indicated by returning False
            logger.error("Authentication failed after retries. Check API key validity and network connection.")
            # You might want to exit here depending on your application's needs
            # return
    except XaiGrokError as e:
        # Catch unexpected errors during the auth process itself (less common)
        logger.error(f"An error occurred during authentication: {e}")
        return

    # --- Sending a Request ---
    messages = [
        {"role": "system", "content": "You are a helpful and slightly sarcastic assistant."},
        {"role": "user", "content": "Explain the concept of recursion in programming like I'm five."}
    ]

    logger.info(f"Sending request with {len(messages)} messages...")
    try:
        # The send_request method also uses the @retry_api_call decorator
        raw_response = connector.send_request(messages)

        # --- Handling the Response ---
        logger.info("Request sent, processing response...")
        processed_response = connector.handle_response(raw_response)

        logger.info(f"Model Used: {processed_response.get('model')}")
        logger.info(f"Response Content:\n{processed_response.get('content')}")
        logger.info(f"Usage: {processed_response.get('usage')}")

    # Handle specific, expected errors from the API call/retry process
    except XaiGrokAuthenticationError as e:
        logger.error(f"Authentication error during request: {e}")
    except XaiGrokRateLimitError as e:
        logger.error(f"Rate limit error during request (retries exhausted): {e}")
    except XaiGrokAPIError as e:
        logger.error(f"API error during request (retries might be exhausted): {e}")
    except XaiGrokNetworkError as e:
        logger.error(f"Network error during request (retries exhausted): {e}")
    except XaiGrokResponseError as e:
        logger.error(f"Invalid response format received: {e}")
    # Handle configuration errors specifically related to the request itself
    except XaiGrokConfigurationError as e:
         logger.error(f"Configuration error sending request (e.g., invalid messages): {e}")
    # Catch any other connector-related errors
    except XaiGrokError as e:
        logger.error(f"A connector error occurred: {e}")
    # Catch unexpected errors not originating from the connector
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}", exc_info=True)

    logger.info("Example finished.")

if __name__ == "__main__":
    main() 