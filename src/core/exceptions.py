class AnalysisProcessingError(Exception):
    """Base exception for analysis processing errors"""
    pass

class TranscriptNotFoundError(AnalysisProcessingError):
    """Raised when transcript cannot be found"""
    pass

class ProfileNotFoundError(AnalysisProcessingError):
    """Raised when profile cannot be found"""
    pass

class APIError(AnalysisProcessingError):
    """Raised when API communication fails"""
    pass

class ResponseParsingError(AnalysisProcessingError):
    """Raised when the API response cannot be parsed"""
    pass

class ResponseValidationError(AnalysisProcessingError):
    """Raised when the API response fails schema validation"""
    pass

class DatabaseError(AnalysisProcessingError):
    """Raised for database related errors"""
    pass 