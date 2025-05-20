class APIError(Exception):
    """Base exception for all API-related errors."""
    def __init__(self, message, status_code=None, details=None):
        super().__init__(message)
        self.status_code = status_code
        self.details = details

    def __str__(self):
        if self.status_code:
            return f"API Error {self.status_code}: {self.args[0]}"
        return f"API Error: {self.args[0]}"

class AuthenticationError(APIError):
    """Raised when API authentication fails (e.g., invalid API key)."""
    def __init__(self, message="Authentication failed", details=None):
        super().__init__(message, status_code=401, details=details)

class AuthorizationError(APIError):
    """Raised when not authorized to access a resource (e.g., permission denied)."""
    def __init__(self, message="Authorization failed", details=None):
        super().__init__(message, status_code=403, details=details)

class InvalidRequestError(APIError):
    """Raised when the request is malformed or contains invalid parameters."""
    def __init__(self, message="Invalid request", details=None):
        super().__init__(message, status_code=400, details=details)

class RateLimitError(APIError):
    """Raised when API rate limits are exceeded."""
    def __init__(self, message="Rate limit exceeded", details=None, retry_after=None):
        super().__init__(message, status_code=429, details=details)
        self.retry_after = retry_after # Seconds to wait before retrying

class APIServerError(APIError):
    """Raised for general server-side errors from the API (5xx errors)."""
    def __init__(self, message="API server error", status_code=500, details=None):
        super().__init__(message, status_code=status_code, details=details)

class APIConnectionError(APIError, ConnectionError):
    """Raised for network connection issues when trying to reach the API."""
    def __init__(self, message="API connection error", details=None):
        super().__init__(message, details=details)
        # ConnectionError part does not take status_code

class APITimeoutError(APIConnectionError):
    """Raised when an API request times out."""
    def __init__(self, message="API request timed out", details=None):
        super().__init__(message, details=details) 