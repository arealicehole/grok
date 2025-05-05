"""Custom exception classes for the Grok Analysis project."""

import sqlite3
import re

# --- XaiGrokConnector Exceptions ---

class XaiGrokError(Exception):
    """Base exception class for all XaiGrokConnector related errors."""
    def __init__(self, message="An error occurred with the XaiGrokConnector", original_exception=None):
        super().__init__(message)
        self.original_exception = original_exception
        self.message = message

    def __str__(self):
        if self.original_exception:
            return f"{self.message}: {self.original_exception}"
        return self.message

class XaiGrokConfigurationError(XaiGrokError):
    """Raised when there is a configuration problem (e.g., missing API key)."""
    def __init__(self, message="Configuration error for XaiGrokConnector", original_exception=None):
        super().__init__(message, original_exception)

class XaiGrokAuthenticationError(XaiGrokError):
    """Raised when authentication with the x.ai API fails."""
    def __init__(self, message="Authentication failed with x.ai API", original_exception=None):
        super().__init__(message, original_exception)

class XaiGrokAPIError(XaiGrokError):
    """Raised for general API errors returned by the x.ai API (e.g., 4xx, 5xx responses)."""
    def __init__(self, message="An error occurred during the x.ai API call", status_code=None, original_exception=None):
        super().__init__(message, original_exception)
        self.status_code = status_code

    def __str__(self):
        base_str = super().__str__()
        if self.status_code:
            return f"{base_str} (Status Code: {self.status_code})"
        return base_str

class XaiGrokNetworkError(XaiGrokError):
    """Raised for network-related issues (e.g., connection errors, timeouts)."""
    def __init__(self, message="A network error occurred while connecting to x.ai API", original_exception=None):
        super().__init__(message, original_exception)

class XaiGrokRateLimitError(XaiGrokAPIError):
    """Raised specifically for rate limit errors (e.g., 429 status code)."""
    def __init__(self, message="Rate limit exceeded for x.ai API", original_exception=None):
        super().__init__(message, status_code=429, original_exception=original_exception)

class XaiGrokResponseError(XaiGrokError):
    """Raised when the API response format is unexpected or invalid."""
    def __init__(self, message="Invalid or unexpected response format from x.ai API", original_exception=None):
        super().__init__(message, original_exception)

# --- Profile Storage Exceptions ---

class ProfileStorageError(Exception):
    """Base exception for profile storage related errors."""
    pass

class ProfileNotFoundError(ProfileStorageError):
    """Raised when a profile is not found."""
    pass

class ProfileValidationError(ProfileStorageError):
    """Raised when profile data fails validation."""
    pass

class ProfileStorageConnectionError(ProfileStorageError):
    """Raised for issues connecting to or interacting with the storage backend."""
    pass

class ProfileConcurrencyError(ProfileStorageError):
    """Raised when a concurrent modification conflict is detected."""
    pass

class ProfileCorruptionError(ProfileStorageError):
    """Raised when data corruption is detected in the storage."""
    pass

class ProfileDatabaseError(ProfileStorageError):
    """Generic database error during profile operations."""
    def __init__(self, message, original_exception=None):
        super().__init__(message)
        self.original_exception = original_exception

class BatchProcessingError(ProfileStorageError):
    """Raised when errors occur during batch processing of profiles."""
    def __init__(self, message, results=None, errors=None):
        super().__init__(message)
        self.results = results or []
        self.errors = errors or []

# --- Schema Handling Exceptions ---

class SchemaError(Exception):
    """Base exception for schema related errors."""
    pass

class SchemaSerializationError(SchemaError):
    """Raised when schema serialization fails."""
    pass

class SchemaDeserializationError(SchemaError):
    """Raised when schema deserialization fails."""
    pass

class SchemaValidationError(SchemaError):
    """Raised when schema validation fails."""
    pass

class SchemaIntegrityError(SchemaError):
    """Raised when schema integrity check (e.g., checksum) fails."""
    pass

# --- Utility Functions ---

# Mapping from sqlite3 exceptions to custom exceptions
SQLITE_ERROR_MAP = {
    sqlite3.IntegrityError: ProfileValidationError, # Includes UNIQUE constraint failures
    sqlite3.OperationalError: ProfileDatabaseError, # Covers issues like "table not found", "database locked"
    sqlite3.DatabaseError: ProfileStorageConnectionError, # General database connection issues
    sqlite3.DataError: ProfileCorruptionError, # Issues with data integrity within the DB
}

def map_sqlite_exception(e: sqlite3.Error) -> ProfileStorageError:
    """Maps an sqlite3 exception to a more specific ProfileStorageError."""
    for sqlite_ex_type, custom_ex_type in SQLITE_ERROR_MAP.items():
        if isinstance(e, sqlite_ex_type):
            # Special handling for locked database
            if isinstance(e, sqlite3.OperationalError) and "database is locked" in str(e).lower():
                 return ProfileConcurrencyError(f"Database locked: {e}", original_exception=e)
            # Special handling for unique constraint
            if isinstance(e, sqlite3.IntegrityError) and "UNIQUE constraint failed" in str(e):
                 # Extract field name if possible (depends on error message format)
                 field_match = re.search(r'profiles\.([\w]+)', str(e))
                 field_name = field_match.group(1) if field_match else 'unknown field'
                 return ProfileValidationError(f"Uniqueness constraint failed for {field_name}: {e}", original_exception=e)

            return custom_ex_type(f"Database error: {e}", original_exception=e)
    # Fallback for unmapped errors
    return ProfileDatabaseError(f"An unexpected database error occurred: {e}", original_exception=e) 