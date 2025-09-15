"""Jubal service contract models."""

from typing import Dict, Any, Optional
from pydantic import BaseModel, Field
from datetime import datetime, timezone


class JubalEnvelope(BaseModel):
    """Standard Jubal data envelope format."""
    job_id: str = Field(..., description="Unique job identifier")
    pipeline_id: Optional[str] = Field(None, description="Optional pipeline identifier")
    data: Dict[str, Any] = Field(..., description="Input data payload")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Request metadata")
    trace: Dict[str, Any] = Field(default_factory=dict, description="Trace information")


class JubalResponse(BaseModel):
    """Standard Jubal response format."""
    job_id: str = Field(..., description="Job identifier from request")
    status: str = Field(..., pattern="^(completed|error|processing)$", description="Processing status")
    data: Optional[Dict[str, Any]] = Field(None, description="Response data payload")
    error: Optional[Dict[str, Any]] = Field(default=None, description="Error information if status=error")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Response metadata")

    @classmethod
    def success(cls, job_id: str, data: Dict[str, Any], metadata: Optional[Dict[str, Any]] = None) -> "JubalResponse":
        """Create a successful response."""
        return cls(
            job_id=job_id,
            status="completed",
            data=data,
            metadata=metadata or {}
        )

    @classmethod
    def create_error(cls, job_id: str, error_code: str, error_message: str, recoverable: bool = True) -> "JubalResponse":
        """Create an error response."""
        return cls(
            job_id=job_id,
            status="error",
            error={
                "code": error_code,
                "message": error_message,
                "recoverable": recoverable,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        )