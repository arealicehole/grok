import logging
import datetime
import uuid
import random
from typing import Any, Optional, Union
import requests # Added for the modified XaiGrokConnector placeholder
import json # Added for handling raw_response storage

# Attempt to import models and connectors
try:
    from src.models import AnalysisJob, JobStatus, AnalysisResult, AnalysisProfile, Transcript # Updated import
    from src.connectors.xai_grok_connector import XaiGrokConnector
    from src.connectors.exceptions import APIError, AuthenticationError, InvalidRequestError, RateLimitError
    from src.core.response_parser import parse_analysis_response, sanitize_response_data
    from src.core.exceptions import (
        AnalysisProcessingError,
        TranscriptNotFoundError,
        ProfileNotFoundError,
        ResponseParsingError,
        ResponseValidationError,
        DatabaseError # Added for completeness
    )
    from src.core.decorators import general_error_handler # Added import
except ImportError as e:
    logging.warning(f"Error importing modules: {e}. Using placeholders for missing classes.")
    # Define placeholders if imports fail
    class JobStatus:
        PENDING = "pending"
        PROCESSING = "processing"
        COMPLETED = "completed"
        FAILED = "failed"

    class AnalysisJob:
        def __init__(self, transcript_id, profile_id, status, id=None, error_message=None, created_at=None, updated_at=None, temporary_instructions=None):
            self.id = id
            self.transcript_id = transcript_id
            self.profile_id = profile_id
            self.status = status
            self.error_message = error_message
            self.created_at = created_at or datetime.datetime.now().isoformat()
            self.updated_at = updated_at or datetime.datetime.now().isoformat()
            self.temporary_instructions = temporary_instructions

    class AnalysisResult:
         def __init__(self, analysis_job_id, raw_response, parsed_data, id=None, created_at=None):
            self.id = id
            self.analysis_job_id = analysis_job_id
            self.raw_response = raw_response
            self.parsed_data = parsed_data
            self.created_at = created_at or datetime.datetime.now().isoformat()
            
    class AnalysisProfile:
        def __init__(self, name: str, instructions: str, schema_definition: str, id: Optional[int] = None, order: Optional[int] = None, created_at: Optional[str] = None, updated_at: Optional[str] = None, last_used_timestamp: Optional[str] = None, usage_count: int = 0):
            self.id = id
            self.name = name
            self.instructions = instructions
            self.schema_definition = schema_definition
            self.order = order
            self.created_at = created_at or datetime.datetime.now().isoformat()
            self.updated_at = updated_at or datetime.datetime.now().isoformat()
            self.last_used_timestamp = last_used_timestamp
            self.usage_count = usage_count

    class Transcript: # Placeholder if import fails
        def __init__(self, text: str, id: Optional[int] = None, name: Optional[str] = None, created_at: Optional[str] = None, updated_at: Optional[str] = None):
            self.id = id
            self.name = name
            self.text = text
            self.created_at = created_at or datetime.datetime.now().isoformat()
            self.updated_at = updated_at or datetime.datetime.now().isoformat()

    # Modified XaiGrokConnector placeholder
    class XaiGrokConnector:
        def __init__(self, api_key="mock_xai_api_key", api_endpoint="https://api.example.com/grok/v1/chat/completions"):
            self.api_key = api_key
            self.api_endpoint = api_endpoint
            self.headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json"
            }
            # It's good practice to use a session object
            self.session = requests.Session()
            self.session.headers.update(self.headers)

        def send_analysis_request(self, transcript_text, profile_instructions, model=None, **kwargs):
            logging.info(f"XaiGrokConnector: Sending analysis request to {self.api_endpoint}")

            # The old error simulation based on profile_instructions can be removed or kept
            # if useful for specific non-HTTP related unit tests of the connector itself.
            # For integration tests of process_transcript_with_profile, we'll rely on mocking requests.post.
            # Example: Keeping one for direct unit testing of this mock connector if desired.
            if "internal_connector_forced_auth_error" in profile_instructions.lower():
                raise AuthenticationError("Forced Authentication Error by instruction")

            payload = {
                "model": model or "grok-1-test", # Example model
                "messages": [
                    {"role": "system", "content": profile_instructions},
                    {"role": "user", "content": transcript_text}
                ],
                "temperature": kwargs.get("temperature", 0.5),
                "max_tokens": kwargs.get("max_tokens", 1500)
            }
            # Allow other kwargs to be passed directly if the API supports them
            payload.update({k: v for k, v in kwargs.items() if k not in ["temperature", "max_tokens"]})

            try:
                # This is the call that will be mocked in integration tests
                response = self.session.post(self.api_endpoint, json=payload, timeout=30) # Using session
                
                # Check for HTTP errors
                response.raise_for_status() 
                
                return response.json() # Return JSON response on success

            except requests.exceptions.HTTPError as http_err:
                status_code = http_err.response.status_code
                error_text = http_err.response.text
                logging.error(f"HTTPError in XaiGrokConnector: {status_code} - {error_text}", exc_info=True)
                if status_code == 401:
                    raise AuthenticationError(f"Authentication failed ({status_code}): {error_text}")
                elif status_code == 429:
                    raise RateLimitError(f"Rate limit exceeded ({status_code}): {error_text}")
                elif 400 <= status_code < 500:
                    raise InvalidRequestError(f"Invalid request ({status_code}): {error_text}")
                else: # 5xx errors or other unexpected HTTP errors
                    raise APIError(f"API request failed with HTTP status {status_code}: {error_text}") from http_err
            except requests.exceptions.Timeout as timeout_err:
                logging.error("Timeout error in XaiGrokConnector", exc_info=True)
                raise APIError("API request timed out.") from timeout_err
            except requests.exceptions.RequestException as req_err: # Catch other request-related errors (e.g., connection error)
                logging.error(f"RequestException in XaiGrokConnector: {req_err}", exc_info=True)
                raise APIError(f"API request failed due to a network issue: {req_err}") from req_err
            except ValueError as json_err: # Catch JSON decoding errors
                logging.error(f"JSONDecodeError in XaiGrokConnector: {json_err}", exc_info=True)
                raise APIError(f"Failed to decode API response as JSON: {json_err}") from json_err

    class APIError(Exception): pass
    class AuthenticationError(APIError): pass # Add placeholder for specific error
    class RateLimitError(APIError): pass      # Add placeholder for specific error
    class InvalidRequestError(APIError): pass # Add placeholder for specific error

# Removed Placeholder for Transcript model as it should be imported now

logger = logging.getLogger(__name__)

# Step 1: Define a Mock DBSession Class
class MockDBSession:
    def __init__(self):
        self.data = {
            "transcripts": {},
            "profiles": {},
            "jobs": {},
            "results": {}
        }
        self.id_counter = 1
        logger.info("MockDBSession initialized.")

    def add(self, obj: Any):
        logger.info(f"MOCK DB: add called with object of type {type(obj)}")
        # Simple logic to add to store if it has an ID
        if hasattr(obj, 'id') and obj.id is not None:
            if isinstance(obj, AnalysisJob): # Assuming AnalysisJob is defined or imported
                self.data["jobs"][obj.id] = obj
            elif isinstance(obj, Transcript): # Assuming Transcript is defined or imported
                 self.data["transcripts"][obj.id] = obj
            elif isinstance(obj, AnalysisProfile): # Assuming AnalysisProfile is defined or imported
                 self.data["profiles"][obj.id] = obj
            elif isinstance(obj, AnalysisResult): # Added for AnalysisResult
                 self.data["results"][obj.id] = obj


    def commit(self):
        logger.info("MOCK DB: commit called.")
        # In a real scenario, this persists changes. Here, it does nothing.

    def flush(self):
        logger.info("MOCK DB: flush called.")
        # In a real scenario, this sends pending SQL to the DB. Here, it does nothing.

    def refresh(self, obj: Any):
        logger.info(f"MOCK DB: refresh called for object {obj}.")
        # In a real scenario, this reloads object state from DB.

    def query(self, model_class: Any): # Basic query simulation
        logger.info(f"MOCK DB: query called for model {model_class.__name__ if hasattr(model_class, '__name__') else model_class}")
        # Return a mock query object that can be further filtered
        class MockQuery:
            def __init__(self, items):
                self._items = items
            def get(self, item_id: Any):
                logger.info(f"MOCK DB Query: get called for ID {item_id}")
                return self._items.get(item_id)
            def filter(self, *criterion): # Very basic filter, ignores criterion
                logger.info(f"MOCK DB Query: filter called with {criterion}")
                return self # Or return a new MockQuery with all items for simplicity
            def first(self):
                logger.info(f"MOCK DB Query: first called")
                return next(iter(self._items.values()), None)


        if model_class == AnalysisJob:
            return MockQuery(self.data["jobs"])
        elif model_class == Transcript:
            return MockQuery(self.data["transcripts"])
        elif model_class == AnalysisProfile:
            return MockQuery(self.data["profiles"])
        elif model_class == AnalysisResult: # Added for AnalysisResult
            return MockQuery(self.data["results"])
        return MockQuery({}) # Empty query for unknown models

    def _get_next_id(self, counter_name: str) -> int:
        self.id_counter += 1
        return self.id_counter

# Step 2: Refine save_analysis_job Function
def save_analysis_job(job: AnalysisJob, db_session: MockDBSession) -> AnalysisJob: # Type hint db_session
    if job.id is None:
        job.id = db_session._get_next_id("jobs") # Use counter from session
        logger.info(f"MOCK DB: Assigned new ID {job.id} to AnalysisJob.")
    job.updated_at = datetime.datetime.now().isoformat()
    db_session.add(job) # Simulate adding to session
    db_session.commit() # Simulate committing
    db_session.refresh(job) # Simulate refreshing state (though mock doesn't change it)
    logger.info(f"MOCK DB: Saved/Updated AnalysisJob with ID {job.id}")
    return job

# Step 3: Refine get_transcript_by_id Function
def get_transcript_by_id(transcript_id: Union[int, str], db_session: MockDBSession) -> Optional[Transcript]: # Type hint
    logger.info(f"MOCK DB: Fetching transcript with ID {transcript_id}")
    try:
        tid = int(transcript_id)
        # Pre-populate if it doesn't exist, for mock purposes.
        # In a real scenario, this pre-population wouldn't exist here.
        if tid not in db_session.data["transcripts"]:
            if tid == 1: # Add a default mock transcript if ID is 1 and not found
                mock_transcript = Transcript(id=tid, name="Sample Transcript 1 (from mock DB)", text="This is a sample transcript content from mock DB.")
                db_session.data["transcripts"][tid] = mock_transcript
                logger.info(f"MOCK DB: Pre-populated transcript {tid} into mock store.")
            else: # If other ID, and not found, return None.
                 return None
        return db_session.query(Transcript).get(tid) # Use mock query
    except ValueError:
        logger.warning(f"MOCK DB: transcript_id '{transcript_id}' is not a valid integer.")
        return None

# Step 4: Refine get_profile_by_id Function
def get_profile_by_id(profile_id: int, db_session: MockDBSession) -> Optional[AnalysisProfile]: # Type hint
    logger.info(f"MOCK DB: Fetching profile with ID {profile_id}")
    # Pre-populate for mock purposes
    if profile_id not in db_session.data["profiles"]:
        if profile_id == 1: # Add a default mock profile if ID is 1 and not found
            mock_profile = AnalysisProfile(
                id=profile_id, 
                name="General Summary (from mock DB)", 
                instructions="Summarize the following transcript.",
                schema_definition='{"summary": "string"}'
            )
            db_session.data["profiles"][profile_id] = mock_profile
            logger.info(f"MOCK DB: Pre-populated profile {profile_id} into mock store.")
        elif profile_id == 2: # Add another mock profile
            mock_profile = AnalysisProfile(
                id=profile_id, 
                name="Key Points Extraction (from mock DB)", 
                instructions="Extract key points from the transcript.",
                schema_definition='{"key_points": ["string"]}'
            )
            db_session.data["profiles"][profile_id] = mock_profile
            logger.info(f"MOCK DB: Pre-populated profile {profile_id} into mock store.")
        else: # If other ID, and not found, return None.
            return None
            
    return db_session.query(AnalysisProfile).get(profile_id) # Use mock query

# Step 5: Update parse_and_store_api_response
def parse_and_store_api_response(job_id: int, raw_response: dict, db_session: MockDBSession, profile_schema: Optional[dict] = None) -> bool: # Type hint
    logger.info(f"Starting to parse and store API response for job_id: {job_id}")
    try:
        # 1. Sanitize (moved before parsing specific content)
        #    This is a general sanitization, specific content parsing comes later.
        #    The exact nature of sanitization here might depend on what `sanitize_response_data` does.
        #    If it expects a string, raw_response might need to be dumped to string first if it's a dict.
        #    Assuming sanitize_response_data can handle a dict or that parse_analysis_response returns string.
        
        # 2. Parse the core content (e.g., the JSON string within the larger API response structure)
        #    This step might vary greatly based on actual API response format.
        #    XaiGrokConnector's mock `send_analysis_request` returns a dict like:
        #    {'choices': [{'message': {'content': '{"summary": "Test summary"}'}}]}
        #    So, we need to extract the 'content' string first.
        
        content_to_parse_str: Optional[str] = None
        if isinstance(raw_response, dict) and \
           raw_response.get("choices") and \
           isinstance(raw_response["choices"], list) and \
           len(raw_response["choices"]) > 0 and \
           isinstance(raw_response["choices"][0], dict) and \
           raw_response["choices"][0].get("message") and \
           isinstance(raw_response["choices"][0]["message"], dict) and \
           isinstance(raw_response["choices"][0]["message"].get("content"), str):
            content_to_parse_str = raw_response["choices"][0]["message"]["content"]
        else:
            logger.error(f"Unexpected raw_response structure for job_id {job_id}. Cannot extract content string.")
            # Attempt to parse raw_response directly if it's a string, or log error if dict but wrong structure.
            if isinstance(raw_response, str): # If raw_response itself is the JSON string
                 content_to_parse_str = raw_response
            else: # If it's a dict but not the expected structure
                raise ResponseParsingError("Raw response structure is not as expected, cannot find content to parse.")


        if content_to_parse_str is None:
            raise ResponseParsingError("Could not extract a string to parse from the raw API response.")

        # Now `content_to_parse_str` should be the JSON string like '{"summary": "Test summary"}'
        parsed_json_content = parse_analysis_response(content_to_parse_str, profile_schema)

        # 3. Sanitize the parsed data (specific sanitization after parsing)
        #    Assuming sanitize_response_data works on the structured data (dict)
        final_sanitized_data = sanitize_response_data(parsed_json_content)

        # 4. Store the result
        _create_and_save_result_object(job_id, raw_response, final_sanitized_data, db_session)
        
        logger.info(f"Successfully parsed and stored API response for job_id: {job_id}")
        return True

    except (ResponseParsingError, ResponseValidationError) as e:
        logger.error(f"Error parsing/validating API response for job {job_id}: {e}", exc_info=True)
        # Optionally, update job status to FAILED here if not handled by a broader error handler
        raise # Re-raise to be caught by process_transcript_with_profile's error handler
    except Exception as e: # Catch any other unexpected errors during parsing/storage
        logger.error(f"Unexpected error during API response processing for job {job_id}: {e}", exc_info=True)
        # Wrap in a known exception type or re-raise
        raise AnalysisProcessingError(f"Unexpected error processing response for job {job_id}: {str(e)}") from e

def save_analysis_result(result: AnalysisResult, db_session: MockDBSession) -> AnalysisResult:
    """Saves an AnalysisResult to the database."""
    if result.id is None:
        result.id = db_session._get_next_id("results")
        logger.info(f"MOCK DB: Assigned new ID {result.id} to AnalysisResult.")
    result.updated_at = datetime.datetime.now().isoformat() # Assuming AnalysisResult has updated_at
    db_session.add(result)
    db_session.commit()
    db_session.refresh(result)
    logger.info(f"MOCK DB: Saved/Updated AnalysisResult with ID {result.id}")
    return result

# Helper function for parse_and_store_api_response (new)
def _create_and_save_result_object(job_id: int, raw_response: dict, parsed_data: dict, db_session: MockDBSession) -> AnalysisResult:
    """
    Creates an AnalysisResult object, sanitizes the parsed data, and saves it.
    """
    logger.info(f"MOCK DB: Creating AnalysisResult for job ID {job_id}")

    # Sanitize the parsed_data before storing it in AnalysisResult
    # The 'parsed_data' argument to this function is the direct output of parse_analysis_response
    # which includes transformations but is not yet sanitized.
    final_sanitized_parsed_data = sanitize_response_data(parsed_data)

    result_id = db_session._get_next_id("results") 
    created_time = datetime.datetime.now().isoformat()

    result = AnalysisResult(
        id=result_id,
        analysis_job_id=job_id,
        raw_response=json.dumps(raw_response),  # Store raw response as JSON string
        parsed_data=final_sanitized_parsed_data, # Store the sanitized version of transformed data
        created_at=created_time
    )
    save_analysis_result(result, db_session) # Use the existing save function
    logger.info(f"MOCK DB: Created and triggered save for AnalysisResult ID {result.id} for job ID {job_id}")
    return result

@general_error_handler(update_job_on_error=True)
def process_transcript_with_profile(
    transcript_id: Union[int, str], 
    profile_id: int, 
    db_session: MockDBSession, # Type hint to MockDBSession
    grok_connector: XaiGrokConnector,
    temporary_instructions: Optional[str] = None, # Added for ad-hoc instructions
    connector_params: Optional[dict] = None # For passing model, temperature, etc.
) -> AnalysisJob:
    """
    Processes a transcript using a specific analysis profile.

    Steps:
    1. Create an AnalysisJob record with 'pending' status.
    2. Fetch Transcript and AnalysisProfile.
    3. Update AnalysisJob status to 'processing'.
    4. Format transcript and profile instructions for the API.
    5. Send request to XaiGrok API.
    6. On success: Parse response, store results in AnalysisResult, update job to 'completed'.
    7. On failure: Update job to 'failed' with error message.
    8. Ensures job status is reliably updated throughout the process.
    """
    logger.info(f"Starting analysis for transcript_id={transcript_id}, profile_id={profile_id}")

    # 1. Create Initial AnalysisJob
    # Ensure profile_id is string for AnalysisJob constructor if it expects that
    # Based on AnalysisJob from src.models.analysis_job_result, profile_id can be Optional[int]
    # For consistency with UUID from AnalysisProfile, let's assume AnalysisJob.profile_id will store it as str
    # or the DB adapter handles UUID type. For now, direct pass or str().
    
    # The AnalysisJob model uses Optional[int] for profile_id.
    # The AnalysisProfile model uses uuid.UUID for id.
    # This is a mismatch. For now, I'll pass profile_id as str(profile_id) to AnalysisJob
    # and assume the database/ORM can handle string representation of UUID for foreign key,
    # or that AnalysisJob.profile_id should ideally be uuid.UUID or str.
    # The AnalysisJob model takes `profile_id: Optional[int]`. This needs to be reconciled.
    # For the mock/placeholder `AnalysisJob`, I'll assume `profile_id` can take the UUID.
    # If using the real `AnalysisJob` from `src.models.analysis_job_result`, this will be an issue.
    # Let's assume for now the actual AnalysisJob model has profile_id as str or UUID compatible.
    # The provided AnalysisJob model has profile_id: Optional[int]. This is a conflict.
    # I will proceed assuming profile_id can be str for AnalysisJob, but this needs fixing in the model.
    
    job = AnalysisJob(
        transcript_id=str(transcript_id), # Ensure transcript_id is string for consistency if job model expects it
        profile_id=profile_id,
        status=JobStatus.PENDING 
    )
    
    # Will use a variable to ensure job is defined in finally block
    # even if initial save_analysis_job fails.
    created_job_id = None

    try:
        # Persist initial job state (e.g., to get an ID and mark as pending)
        job = save_analysis_job(job, db_session)
        created_job_id = job.id # Store ID after creation
        logger.info(f"Created AnalysisJob with ID {job.id}, status PENDING.")

        # 2. Fetch Transcript and AnalysisProfile
        transcript = get_transcript_by_id(transcript_id, db_session)
        profile = get_profile_by_id(profile_id, db_session) # profile_id is int

        if not transcript:
            job.status = JobStatus.FAILED
            job.error_message = f"Transcript with id {transcript_id} not found."
            logger.error(job.error_message)
            # No return here, finally block will save
        elif not profile:
            job.status = JobStatus.FAILED
            job.error_message = f"AnalysisProfile with id {profile_id} not found."
            logger.error(job.error_message)
            # No return here, finally block will save
        else:
            # 3. Update AnalysisJob status to 'processing'
            job.status = JobStatus.PROCESSING
            job = save_analysis_job(job, db_session) # Save status update
            logger.info(f"AnalysisJob {job.id} status updated to PROCESSING.")

            # 4. Format transcript text and profile instructions
            transcript_text = transcript.text
            profile_instructions = profile.instructions
            
            # 5. Use XaiGrokConnector (now passed as an argument)
            # connector = XaiGrokConnector() # Removed direct instantiation
            
            logger.info(f"Sending analysis request for job {job.id} to XaiGrok API using provided connector.")
            api_response = grok_connector.send_analysis_request( # Use the injected connector
                transcript_text=transcript_text,
                profile_instructions=profile_instructions
            )

            # 6. Handle API Response (Success path from API call)
            logger.info(f"Received API response for job {job.id}.")
            
            parsing_successful = parse_and_store_api_response(job.id, api_response, db_session)

            if parsing_successful:
                job.status = JobStatus.COMPLETED
                logger.info(f"AnalysisJob {job.id} successfully completed.")
            else:
                job.status = JobStatus.FAILED
                job.error_message = "Failed to parse or store API response after successful API call."
                logger.error(f"Error for job {job.id}: {job.error_message}")
                
    except AuthenticationError as e: # Catch specific AuthenticationError
        logger.error(f"AuthenticationError during analysis for job {created_job_id if created_job_id else 'new_unidentified'}: {e}", exc_info=True)
        if created_job_id:
            job.status = JobStatus.FAILED
            job.error_message = f"Authentication Error: {str(e)}"
    except RateLimitError as e: # Catch specific RateLimitError
        logger.error(f"RateLimitError during analysis for job {created_job_id if created_job_id else 'new_unidentified'}: {e}", exc_info=True)
        if created_job_id:
            job.status = JobStatus.FAILED
            job.error_message = f"Rate Limit Error: {str(e)}"
    except InvalidRequestError as e: # Catch specific InvalidRequestError
        logger.error(f"InvalidRequestError during analysis for job {created_job_id if created_job_id else 'new_unidentified'}: {e}", exc_info=True)
        if created_job_id:
            job.status = JobStatus.FAILED
            job.error_message = f"Invalid Request Error: {str(e)}"
    except APIError as e: # Catch specific API errors from XaiGrokConnector
        logger.error(f"APIError during analysis for job {created_job_id if created_job_id else 'new_unidentified'}: {e}", exc_info=True)
        if created_job_id:
            job.status = JobStatus.FAILED
            job.error_message = f"API Error: {str(e)}"
            
    except Exception as e:
        logger.error(f"Unexpected error during analysis for job {created_job_id if created_job_id else 'new_unidentified'}: {e}", exc_info=True)
        if created_job_id: # If job was created
            job.status = JobStatus.FAILED
            job.error_message = f"Unexpected error: {str(e)}"
            
    finally:
        # 8. Save final AnalysisJob state
        if created_job_id is not None: # Only save if job was successfully created initially
            job = save_analysis_job(job, db_session) # Save final state
            logger.info(f"Finalized AnalysisJob {job.id} with status {job.status if isinstance(job.status, str) else job.status.value}.")
        elif 'job' in locals() and job is not None: # Job object exists but might not have an ID if first save failed
             logger.warning(f"AnalysisJob object existed but was not saved to DB initially or its ID is unknown. Attempting to log its state: {job.status}")
        else: # If job creation itself failed before an ID was assigned (e.g. initial save_analysis_job threw error)
             logger.error(f"AnalysisJob creation failed or job object is not available. Transcript: {transcript_id}, Profile: {profile_id}")
             # If job object doesn't exist or has no ID, we can't save it.
             # A robust system might create a minimal FAILED job entry here if one doesn't exist.
             # For this implementation, if initial save fails, job won't be saved in finally.

    return job 