import functools
import logging
from typing import Type, List, Callable, Any, Optional

# Assuming your custom exceptions are here
from src.core.exceptions import AnalysisProcessingError, APIError # Add more as needed
# Assuming your AnalysisJob model is here, or a base class/interface
from src.models.analysis_job import AnalysisJob, JobStatus

logger = logging.getLogger(__name__)

def general_error_handler(
    update_job_status_on_error: bool = True,
    default_error_status: JobStatus = JobStatus.FAILED,
    log_level: int = logging.ERROR,
    exceptions_to_catch: Optional[List[Type[Exception]]] = None
):
    """
    A general error handling decorator for functions, especially those interacting with AnalysisJob.

    Args:
        update_job_status_on_error: If True, attempts to find an AnalysisJob object
                                    in the decorated function's arguments or return value
                                    (if it itself returns a job) and update its status on error.
        default_error_status: The JobStatus to set if an error occurs and job update is enabled.
        log_level: The logging level for caught exceptions.
        exceptions_to_catch: A list of specific exception types to catch.
                             If None, catches all Exceptions.
    """
    # Ensure exceptions_to_catch is a tuple for the except block
    catch_these = tuple(exceptions_to_catch) if exceptions_to_catch else (Exception,)

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            job_instance: Optional[AnalysisJob] = None
            
            # Attempt to find AnalysisJob in kwargs or args for status updates
            if update_job_status_on_error:
                if 'job' in kwargs and isinstance(kwargs['job'], AnalysisJob):
                    job_instance = kwargs['job']
                else:
                    for arg in args:
                        if isinstance(arg, AnalysisJob):
                            job_instance = arg
                            break
            
            try:
                result = func(*args, **kwargs)
                # If the function returns a job, it might be the primary one to update
                if update_job_status_on_error and isinstance(result, AnalysisJob) and not job_instance:
                    job_instance = result
                return result
            except catch_these as e:
                error_message = f"Error in {func.__name__}: {type(e).__name__} - {str(e)}"
                logger.log(log_level, error_message, exc_info=True) # Add exc_info for traceback

                if update_job_status_on_error and job_instance:
                    try:
                        job_instance.status = default_error_status
                        job_instance.error_message = error_message
                        # Potentially call a save method if the job object requires explicit saving
                        # e.g., if hasattr(job_instance, 'save') and callable(job_instance.save):
                        #     job_instance.save()
                        logger.info(f"Updated job {getattr(job_instance, 'id', 'N/A')} status to {default_error_status.value} due to error.")
                    except Exception as job_update_err:
                        logger.error(f"Failed to update job status for {getattr(job_instance, 'id', 'N/A')}: {job_update_err}", exc_info=True)
                
                # Re-raise the original exception or a custom one if preferred
                # For example, wrap it in a more generic AnalysisProcessingError if not already one.
                if not isinstance(e, AnalysisProcessingError):
                    raise AnalysisProcessingError(error_message) from e
                else:
                    raise # Re-raise the original, more specific AnalysisProcessingError subclass
        return wrapper
    return decorator

# Example Usage (conceptual):
# @general_error_handler(exceptions_to_catch=[APIError, ValueError])
# def my_function_that_might_fail(job: AnalysisJob, some_param: str):
#     # ... function logic ...
#     if some_param == "bad":
#         raise ValueError("Bad parameter provided")
#     # ...
#     return job 