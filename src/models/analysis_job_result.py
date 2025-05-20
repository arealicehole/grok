import datetime
import enum
from typing import Optional, Dict, Any, Union

class JobStatus(enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class AnalysisJob:
    """Represents a job for analyzing a transcript."""
    def __init__(self,
                 transcript_id: Union[int, str],
                 profile_id: Optional[int] = None,      # Made optional, validation will check logic
                 status: JobStatus = JobStatus.PENDING,
                 id: Optional[int] = None,
                 created_at: Optional[str] = None,
                 updated_at: Optional[str] = None,
                 error_message: Optional[str] = None,
                 temporary_instructions: Optional[str] = None):
        if not transcript_id:
            raise ValueError("AnalysisJob: transcript_id cannot be empty.")
        if not isinstance(status, JobStatus):
            raise ValueError(f"AnalysisJob: status must be a JobStatus enum member, got {status}")
        if profile_id is None and temporary_instructions is None:
            raise ValueError("AnalysisJob: Either profile_id or temporary_instructions must be provided.")
        if profile_id is not None and temporary_instructions is not None:
            raise ValueError("AnalysisJob: Both profile_id and temporary_instructions cannot be provided simultaneously.")

        self.id: Optional[int] = id
        self.transcript_id: Union[int, str] = transcript_id
        self.profile_id: Optional[int] = profile_id
        self.temporary_instructions: Optional[str] = temporary_instructions
        self.status: JobStatus = status
        self.created_at: str = created_at or datetime.datetime.now().isoformat()
        self.updated_at: str = updated_at or datetime.datetime.now().isoformat()
        self.error_message: Optional[str] = error_message

    def to_dict(self) -> Dict[str, Any]:
        """Converts the analysis job to a dictionary."""
        return {
            "id": self.id,
            "transcript_id": self.transcript_id,
            "profile_id": self.profile_id,
            "temporary_instructions": self.temporary_instructions,
            "status": self.status.value, # Store enum value
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "error_message": self.error_message,
        }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> 'AnalysisJob':
        # Basic validation for status if it's coming from a string value
        status_val = data.get("status", "pending")
        try:
            job_status = JobStatus(status_val)
        except ValueError as e:
            # Fallback or re-raise, depending on desired strictness
            # For now, let's default to PENDING if invalid, or one could raise an error
            # print(f"Warning: Invalid status '{status_val}' in data. Defaulting to PENDING. Error: {e}")
            # job_status = JobStatus.PENDING
            raise ValueError(f"Invalid status value '{status_val}' provided to AnalysisJob.from_dict. Error: {e}") from e

        return AnalysisJob(
            id=data.get("id"),
            transcript_id=data.get("transcript_id"),
            profile_id=data.get("profile_id"),
            temporary_instructions=data.get("temporary_instructions"),
            status=job_status,
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
            error_message=data.get("error_message"),
        )

    def __repr__(self) -> str:
        """Returns a string representation of the analysis job."""
        return (f"AnalysisJob(id={self.id}, status='{self.status.value}', "
                f"transcript_id='{self.transcript_id}', profile_id={self.profile_id}, "
                f"created_at='{self.created_at}', updated_at='{self.updated_at}')")

class AnalysisResult:
    """Represents the result of an analysis job."""
    def __init__(self,
                 analysis_job_id: int,
                 raw_response: Union[Dict[str, Any], str],
                 parsed_data: Optional[Union[Dict[str, Any], str]] = None,
                 id: Optional[int] = None,
                 created_at: Optional[str] = None,
                 status: str = "Success"
                ):
        if analysis_job_id is None: # Check for None explicitly, as 0 is a valid ID.
            raise ValueError("AnalysisResult: analysis_job_id cannot be None.")
        if not raw_response:
            raise ValueError("AnalysisResult: raw_response cannot be empty.")

        self.id: Optional[int] = id
        self.analysis_job_id: int = analysis_job_id
        self.raw_response: Union[Dict[str, Any], str] = raw_response
        self.parsed_data: Optional[Union[Dict[str, Any], str]] = parsed_data
        self.created_at: str = created_at or datetime.datetime.now().isoformat()
        self.status: str = status

    def to_dict(self) -> Dict[str, Any]:
        """Converts the analysis result to a dictionary."""
        return {
            "id": self.id,
            "analysis_job_id": self.analysis_job_id,
            "raw_response": self.raw_response,
            "parsed_data": self.parsed_data,
            "created_at": self.created_at,
            "status": self.status,
        }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> 'AnalysisResult':
        """Creates an AnalysisResult from a dictionary."""
        return AnalysisResult(
            id=data.get("id"),
            analysis_job_id=data.get("analysis_job_id"),
            raw_response=data.get("raw_response"),
            parsed_data=data.get("parsed_data"),
            created_at=data.get("created_at"),
            status=data.get("status", "Success")
        )

    def __repr__(self) -> str:
        """Returns a string representation of the analysis result."""
        return (f"AnalysisResult(id={self.id}, analysis_job_id={self.analysis_job_id}, "
                f"status='{self.status}', created_at='{self.created_at}')") 