# Placeholder for Pytest tests for analysis_processor.py 

import pytest
from unittest.mock import patch, MagicMock
import datetime

# Attempt to import actual classes; fall back to mocks if not found (e.g., in CI/CD minimal env)
try:
    from src.core.analysis_processor import (
        process_transcript_with_profile,
        get_transcript_by_id,
        get_profile_by_id,
        save_analysis_job,
        parse_and_store_api_response,
        MockDBSession, # Assuming this is the mock DB session used
        JobStatus,
        AnalysisJob,
        AnalysisResult,
        Transcript,
        AnalysisProfile,
        XaiGrokConnector
    )
    from src.connectors.exceptions import APIError, AuthenticationError, RateLimitError, InvalidRequestError
    from src.core.exceptions import ResponseParsingError, ResponseValidationError, AnalysisProcessingError
except ImportError:
    # Define minimal placeholders if actual imports fail
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
        def to_dict(self): return self.__dict__


    class AnalysisResult:
        def __init__(self, analysis_job_id, raw_response, parsed_data, id=None, created_at=None):
            self.id = id
            self.analysis_job_id = analysis_job_id
            self.raw_response = raw_response
            self.parsed_data = parsed_data
            self.created_at = created_at or datetime.datetime.now().isoformat()

    class Transcript:
        def __init__(self, id, text, name="Test Transcript"):
            self.id = id
            self.text = text
            self.name = name

    class AnalysisProfile:
        def __init__(self, id, name, instructions, schema_definition):
            self.id = id
            self.name = name
            self.instructions = instructions
            self.schema_definition = schema_definition
            
    class XaiGrokConnector:
        def __init__(self, api_key="dummy_key"): self.api_key = api_key
        def send_analysis_request(self, transcript_text, profile_instructions, **kwargs): pass

    class MockDBSession: # Simplified Mock
        def __init__(self): self.data = {"jobs":{}, "results":{}, "transcripts":{}, "profiles":{}}; self.id_counter = 0
        def _get_next_id(self, store): self.id_counter += 1; return self.id_counter
        def add(self, obj): 
            if isinstance(obj, AnalysisJob): self.data["jobs"][obj.id] = obj
            elif isinstance(obj, AnalysisResult): self.data["results"][obj.id] = obj
        def commit(self): pass
        def flush(self): pass
        def refresh(self, obj): pass
        def query(self, model_class):
            class MockQuery:
                def __init__(self, items): self._items = items
                def get(self, item_id): return self._items.get(item_id)
            if model_class == Transcript: return MockQuery(self.data["transcripts"])
            if model_class == AnalysisProfile: return MockQuery(self.data["profiles"])
            return MockQuery({})


    class APIError(Exception): pass
    class AuthenticationError(APIError): pass
    class RateLimitError(APIError): pass
    class InvalidRequestError(APIError): pass
    class ResponseParsingError(Exception): pass
    class ResponseValidationError(Exception): pass
    class AnalysisProcessingError(Exception): pass


@pytest.fixture
def mock_db_session():
    session = MockDBSession()
    # Pre-populate with some data for tests
    session.data["transcripts"][1] = Transcript(id=1, text="This is a sample transcript.")
    session.data["profiles"][1] = AnalysisProfile(id=1, name="Test Profile", instructions="Summarize this.", schema_definition='{"summary": "string"}')
    return session

@pytest.fixture
def mock_grok_connector():
    connector = MagicMock(spec=XaiGrokConnector)
    return connector

# --- Test Success Scenario ---
def test_process_transcript_with_profile_success(mock_db_session, mock_grok_connector):
    transcript_id = 1
    profile_id = 1
    
    mock_api_response = {
        "choices": [{
            "message": {
                "content": '{"summary": "This is the Grok summary."}'
            }
        }]
    }
    mock_grok_connector.send_analysis_request.return_value = mock_api_response

    # Mock parse_and_store_api_response to return True for success
    with patch('src.core.analysis_processor.parse_and_store_api_response', return_value=True) as mock_parse_store, \
         patch('src.core.analysis_processor.save_analysis_job', side_effect=lambda job, db: job) as mock_save_job:

        job = process_transcript_with_profile(transcript_id, profile_id, mock_db_session, mock_grok_connector)

        assert job is not None
        assert job.status == JobStatus.COMPLETED
        assert job.error_message is None
        mock_grok_connector.send_analysis_request.assert_called_once_with(
            transcript_text="This is a sample transcript.",
            profile_instructions="Summarize this."
        )
        mock_parse_store.assert_called_once()
        # Check that save_analysis_job was called multiple times (initial, processing, final)
        assert mock_save_job.call_count >= 3


# --- Test Missing Data Scenarios ---
def test_process_transcript_not_found(mock_db_session, mock_grok_connector):
    job = process_transcript_with_profile(99, 1, mock_db_session, mock_grok_connector)
    assert job.status == JobStatus.FAILED
    assert "Transcript with id 99 not found" in job.error_message

def test_process_profile_not_found(mock_db_session, mock_grok_connector):
    job = process_transcript_with_profile(1, 99, mock_db_session, mock_grok_connector)
    assert job.status == JobStatus.FAILED
    assert "AnalysisProfile with id 99 not found" in job.error_message

# --- Test Temporary Instructions Scenario ---
def test_process_with_temporary_instructions_success(mock_db_session, mock_grok_connector):
    transcript_id = 1
    temp_instructions = "Summarize this briefly."
    
    # Ensure transcript 1 exists in mock_db_session
    mock_db_session.data["transcripts"][1] = Transcript(id=1, text="This is a detailed sample transcript for temp instructions.")

    mock_api_response = {
        "choices": [{
            "message": {
                "content": '{"summary": "Brief summary from temp instructions."}'
            }
        }]
    }
    mock_grok_connector.send_analysis_request.return_value = mock_api_response

    # Mock get_profile_by_id to return None, as profile_id will be None
    with patch('src.core.analysis_processor.get_profile_by_id', return_value=None) as mock_get_profile, \
         patch('src.core.analysis_processor.parse_and_store_api_response', return_value=True) as mock_parse_store, \
         patch('src.core.analysis_processor.save_analysis_job', side_effect=lambda job, db: job) as mock_save_job:

        job = process_transcript_with_profile(
            transcript_id=transcript_id, 
            profile_id=None,  # No profile_id
            db_session=mock_db_session, 
            grok_connector=mock_grok_connector,
            temporary_instructions=temp_instructions
        )

        assert job is not None
        assert job.status == JobStatus.COMPLETED
        assert job.error_message is None
        assert job.temporary_instructions == temp_instructions # Check if temp instructions were stored/used
        
        # get_profile_by_id should not be called if profile_id is None and temp_instructions are present
        # However, the current process_transcript_with_profile logic calls get_profile_by_id regardless
        # and then checks if profile is None. Let's verify it was called with None.
        mock_get_profile.assert_called_once_with(None, mock_db_session)
        
        mock_grok_connector.send_analysis_request.assert_called_once_with(
            transcript_text="This is a detailed sample transcript for temp instructions.",
            profile_instructions=temp_instructions # Should use temp_instructions
        )
        mock_parse_store.assert_called_once()
        assert mock_save_job.call_count >= 3


# --- Test Connector Params Scenario ---
def test_process_with_connector_params(mock_db_session, mock_grok_connector):
    transcript_id = 1
    profile_id = 1
    connector_params = {"model": "grok-custom-model", "temperature": 0.5}

    # Ensure transcript 1 and profile 1 exist
    mock_db_session.data["transcripts"][1] = Transcript(id=1, text="Sample text for connector params test.")
    mock_db_session.data["profiles"][1] = AnalysisProfile(id=1, name="ProfileForParams", instructions="Analyze with custom params.", schema_definition='{}')

    mock_api_response = {"choices": [{"message": {"content": '{"result": "ok"}'}}]}
    mock_grok_connector.send_analysis_request.return_value = mock_api_response

    with patch('src.core.analysis_processor.parse_and_store_api_response', return_value=True), \
         patch('src.core.analysis_processor.save_analysis_job', side_effect=lambda job, db: job):

        job = process_transcript_with_profile(
            transcript_id=transcript_id, 
            profile_id=profile_id, 
            db_session=mock_db_session, 
            grok_connector=mock_grok_connector,
            connector_params=connector_params
        )

        assert job.status == JobStatus.COMPLETED
        mock_grok_connector.send_analysis_request.assert_called_once_with(
            transcript_text="Sample text for connector params test.",
            profile_instructions="Analyze with custom params.",
            model="grok-custom-model", # Check if extra params are passed
            temperature=0.5
        )

# --- Test API Error Scenarios ---
@pytest.mark.parametrize("api_exception, error_message_part", [
    (APIError("Generic API failure"), "API Error: Generic API failure"),
    (AuthenticationError("Auth failed"), "Authentication Error: Auth failed"),
    (RateLimitError("Rate limited"), "Rate Limit Error: Rate limited"),
    (InvalidRequestError("Bad request"), "Invalid Request Error: Bad request"),
])
def test_process_transcript_api_errors(mock_db_session, mock_grok_connector, api_exception, error_message_part):
    mock_grok_connector.send_analysis_request.side_effect = api_exception

    job = process_transcript_with_profile(1, 1, mock_db_session, mock_grok_connector)

    assert job.status == JobStatus.FAILED
    assert error_message_part in job.error_message

# --- Test Response Parsing/Validation Error Scenario ---
def test_process_transcript_parsing_error(mock_db_session, mock_grok_connector):
    mock_grok_connector.send_analysis_request.return_value = {"choices": [{"message": {"content": "invalid json"}}]}

    with patch('src.core.analysis_processor.parse_analysis_response', side_effect=ResponseParsingError("Bad format")) as mock_parse, \
         patch('src.core.analysis_processor.parse_and_store_api_response', side_effect=ResponseParsingError("Bad format")):
        job = process_transcript_with_profile(1, 1, mock_db_session, mock_grok_connector)
    
    assert job.status == JobStatus.FAILED
    # The error message will be caught by the general_error_handler, which wraps the original error.
    # It might also be that parse_and_store_api_response catches it and sets a specific message.
    # The general_error_handler on process_transcript_with_profile will catch the ResponseParsingError raised by parse_and_store_api_response
    assert "ResponseParsingError: Bad format" in job.error_message or "Failed to parse or store API response" in job.error_message


def test_process_transcript_validation_error(mock_db_session, mock_grok_connector):
    mock_grok_connector.send_analysis_request.return_value = {"choices": [{"message": {"content": '{"wrong_field": "data"}'}}]}

    # Mock parse_and_store_api_response to simulate a validation error
    with patch('src.core.analysis_processor.parse_and_store_api_response', side_effect=ResponseValidationError("Schema mismatch")) as mock_parse_store:
        job = process_transcript_with_profile(1, 1, mock_db_session, mock_grok_connector)

    assert job.status == JobStatus.FAILED
    assert "ResponseValidationError: Schema mismatch" in job.error_message or "Failed to parse or store API response" in job.error_message


# --- Test Unexpected Error Scenario ---
def test_process_transcript_unexpected_error(mock_db_session, mock_grok_connector):
    mock_grok_connector.send_analysis_request.side_effect = Exception("Highly unexpected error")

    job = process_transcript_with_profile(1, 1, mock_db_session, mock_grok_connector)

    assert job.status == JobStatus.FAILED
    assert "Unexpected error: Highly unexpected error" in job.error_message


# --- Test parse_and_store_api_response returning False ---
def test_process_parse_and_store_returns_false(mock_db_session, mock_grok_connector):
    transcript_id = 1
    profile_id = 1

    # Ensure transcript and profile exist
    mock_db_session.data["transcripts"][1] = Transcript(id=1, text="Sample content.")
    mock_db_session.data["profiles"][1] = AnalysisProfile(id=1, name="TestProfile", instructions="Do stuff", schema_definition='{}')

    mock_api_response = {"choices": [{"message": {"content": '{"data": "valid_looking_content"}'}}]}
    mock_grok_connector.send_analysis_request.return_value = mock_api_response

    # Mock parse_and_store_api_response to return False
    with patch('src.core.analysis_processor.parse_and_store_api_response', return_value=False) as mock_parse_store, \
         patch('src.core.analysis_processor.save_analysis_job', side_effect=lambda job, db: job) as mock_save_job:

        job = process_transcript_with_profile(transcript_id, profile_id, mock_db_session, mock_grok_connector)

        assert job.status == JobStatus.FAILED
        assert job.error_message == "Failed to parse or store API response after successful API call."
        mock_parse_store.assert_called_once_with(job.id, mock_api_response, mock_db_session)


# --- Test Initial Job Save Failure (less common, but good to consider) ---
def test_process_transcript_initial_job_save_fails(mock_db_session, mock_grok_connector):
    with patch('src.core.analysis_processor.save_analysis_job', side_effect=IOError("DB unavailable")) as mock_save_job:
        # Expect the error_handler to catch this and not proceed, or for the initial save failure to propagate
        with pytest.raises(AnalysisProcessingError) as exc_info: # Assuming general_error_handler wraps it
             process_transcript_with_profile(1, 1, mock_db_session, mock_grok_connector)
        
        assert "IOError: DB unavailable" in str(exc_info.value) # or "AnalysisProcessingError: IOError: DB unavailable"
        mock_save_job.assert_called_once() # Should fail on the first attempt to save


# --- Test save_analysis_job failures at different stages ---
def test_process_save_job_fails_on_processing_update(mock_db_session, mock_grok_connector):
    transcript_id = 1
    profile_id = 1
    mock_db_session.data["transcripts"][1] = Transcript(id=1, text="Sample")
    mock_db_session.data["profiles"][1] = AnalysisProfile(id=1, name="Prof", instructions="Ins", schema_definition='{}')

    # Configure save_analysis_job to fail on the second call (which should be the PROCESSING update)
    # The first call is for initial PENDING save.
    mock_save_job_calls = []
    def save_job_side_effect_for_processing_fail(job, db_session):
        mock_save_job_calls.append(job.status)
        if len(mock_save_job_calls) == 2 and job.status == JobStatus.PROCESSING:
            raise IOError("DB error on PROCESSING update")
        if job.id is None:
            job.id = mock_db_session._get_next_id() # Simulate ID assignment on first call
        return job

    with patch('src.core.analysis_processor.save_analysis_job', side_effect=save_job_side_effect_for_processing_fail) as mock_save_job_actual, \
         patch('src.core.analysis_processor.parse_and_store_api_response', return_value=True): # Not relevant here
        
        job = process_transcript_with_profile(transcript_id, profile_id, mock_db_session, mock_grok_connector)

        # The general_error_handler on process_transcript_with_profile should catch the IOError
        # and set the job status to FAILED.
        assert job.status == JobStatus.FAILED
        assert "IOError: DB error on PROCESSING update" in job.error_message
        assert len(mock_save_job_calls) >= 2 # Initial save, attempted processing save, and final save in finally block
        # The final save in the `finally` block will attempt to save the FAILED status.
        # The error message should be from the PROCESSING update failure.

def test_process_save_job_fails_on_completion_update(mock_db_session, mock_grok_connector):
    transcript_id = 1
    profile_id = 1
    mock_db_session.data["transcripts"][1] = Transcript(id=1, text="Sample")
    mock_db_session.data["profiles"][1] = AnalysisProfile(id=1, name="Prof", instructions="Ins", schema_definition='{}')

    mock_api_response = {"choices": [{"message": {"content": '{"data": "success"}'}}]}
    mock_grok_connector.send_analysis_request.return_value = mock_api_response

    mock_save_job_calls = []
    # Let initial PENDING and PROCESSING saves succeed.
    # Fail when parse_and_store_api_response has returned True and status is about to be COMPLETED.
    # This is tricky because the save_analysis_job for COMPLETED is inside the `finally` block
    # in conjunction with `parse_and_store_api_response` setting it before the final save.
    # The actual save_analysis_job for COMPLETED happens in the finally block.
    # The `process_transcript_with_profile` will set job.status = JobStatus.COMPLETED *before* the final save.

    def save_job_side_effect_for_completion_fail(job, db_session):
        mock_save_job_calls.append(job.status)
        # The sequence of statuses being saved could be: PENDING, PROCESSING, COMPLETED (in finally)
        # Let's make it fail when it tries to save COMPLETED.
        if job.status == JobStatus.COMPLETED and len(mock_save_job_calls) >= 3: # Assuming 3rd or later call with COMPLETED status
            raise IOError("DB error on COMPLETED update")
        if job.id is None:
            job.id = mock_db_session._get_next_id()
        return job

    with patch('src.core.analysis_processor.save_analysis_job', side_effect=save_job_side_effect_for_completion_fail) as mock_save_job_actual, \
         patch('src.core.analysis_processor.parse_and_store_api_response', return_value=True) as mock_parse_store:

        job = process_transcript_with_profile(transcript_id, profile_id, mock_db_session, mock_grok_connector)

        # Even if the save in `finally` for COMPLETED fails, the general_error_handler has already exited.
        # The `process_transcript_with_profile` will return the job object.
        # The job.status would have been set to COMPLETED before the `finally` block's save_analysis_job is called.
        # The error from save_analysis_job inside `finally` will propagate out of process_transcript_with_profile
        # if not caught by general_error_handler again (which it isn't, as finally is outside its try).
        # So, we expect an IOError here.
        
        # Re-thinking: The @general_error_handler wraps the whole function body including its own try/except/finally.
        # So, an error in the final `save_analysis_job` within the `finally` block of `process_transcript_with_profile`
        # should still be caught by the decorator, and the job object returned by the function should reflect FAILED.

        assert job.status == JobStatus.FAILED
        assert "IOError: DB error on COMPLETED update" in job.error_message
        mock_parse_store.assert_called_once()


# --- Test decorator's effect ---
# This implicitly tests the @general_error_handler on process_transcript_with_profile
def test_general_error_handler_updates_job_status_on_error(mock_db_session):
    # Use a simplified function to test the decorator's behavior if it were applied elsewhere
    # For process_transcript_with_profile, this is covered by other tests.
    # This is more of a direct test of the decorator if it were isolated.
    
    # Let's assume we have a job object
    mock_job = AnalysisJob(transcript_id="tid", profile_id=1, status=JobStatus.PROCESSING, id="job1")

    # We need to import general_error_handler if it's not already.
    # Assuming it's available from src.core.decorators for this conceptual test
    try:
        from src.core.decorators import general_error_handler
    except ImportError:
        pytest.skip("Skipping decorator direct test as general_error_handler not found")

    @general_error_handler(update_job_on_error=True)
    def decorated_function_throws_error(job_param):
        raise ValueError("Something went wrong inside")

    with pytest.raises(AnalysisProcessingError) as exc_info: # general_error_handler wraps it
        # We need to pass the job object in a way the decorator can find it.
        # The decorator looks for 'job' in kwargs or in args if it has 'status' and 'error_message'.
        # So, we pass it as a keyword argument.
        decorated_function_throws_error(job_param=mock_job) 
        
    assert mock_job.status == JobStatus.FAILED
    assert "ValueError: Something went wrong inside" in mock_job.error_message
    assert "ValueError: Something went wrong inside" in str(exc_info.value)
    assert isinstance(exc_info.value.__cause__, ValueError)


# Test that a non-AnalysisProcessingError is wrapped
def test_general_error_handler_wraps_non_analysis_processing_error(mock_db_session):
    try:
        from src.core.decorators import general_error_handler
    except ImportError:
        pytest.skip("Skipping decorator direct test as general_error_handler not found")

    @general_error_handler()
    def function_raising_standard_error():
        raise TypeError("A standard Python error")

    with pytest.raises(AnalysisProcessingError) as exc_info:
        function_raising_standard_error()
    
    assert "TypeError: A standard Python error" in str(exc_info.value)
    assert isinstance(exc_info.value.__cause__, TypeError) 