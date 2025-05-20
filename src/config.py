import os

# XAI Grok API Configuration
XAI_API_KEY = os.environ.get("XAI_API_KEY")
XAI_API_ENDPOINT = os.environ.get("XAI_API_ENDPOINT", "https://api.x.ai/v1/chat/completions")
DEFAULT_GROK_MODEL = os.environ.get("DEFAULT_GROK_MODEL", "grok-1")

# Request settings
REQUEST_TIMEOUT_SECONDS = int(os.environ.get("REQUEST_TIMEOUT_SECONDS", 30))
MAX_RETRIES = int(os.environ.get("MAX_RETRIES", 3))

# Logging Configuration (Basic)
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()

# Example check for essential config
if not XAI_API_KEY:
    print("Warning: XAI_API_KEY environment variable is not set. XaiGrokConnector may not function.") 