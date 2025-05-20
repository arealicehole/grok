import pytest
import requests
import time # For checking sleep calls
from unittest.mock import patch, MagicMock
from typing import Type # For type hinting exceptions

from src.connectors.xai_grok_connector import XaiGrokConnector 
from src.connectors.exceptions import APIError, AuthenticationError, InvalidRequestError, RateLimitError, AuthorizationError

@pytest.fixture
def connector() -> XaiGrokConnector:
    """Provides a XaiGrokConnector instance with default retry settings for testing."""
    return XaiGrokConnector(api_key="test_api_key_placeholder")

@pytest.fixture
def connector_no_retry() -> XaiGrokConnector:
    """Provides a XaiGrokConnector instance with max_retries=0."""
    return XaiGrokConnector(api_key="test_api_key_placeholder", max_retries=0)


# --- Test Successful Scenarios ---
def test_send_analysis_request_success(connector: XaiGrokConnector):
    mock_response_json = {"choices": [{"message": {"content": '{"summary": "Test summary"}'}}]}
    mock_response = MagicMock(spec=requests.Response)
    mock_response.status_code = 200
    mock_response.reason = "OK"
    mock_response.json.return_value = mock_response_json
    mock_response.text = '{"choices": [{"message": {"content": '{"summary": "Test summary"}'}}]}'

    with patch.object(connector.session, 'post', return_value=mock_response) as mock_post:
        response = connector.send_analysis_request(
            transcript_text="Test transcript",
            profile_instructions="Test instructions"
        )
        mock_post.assert_called_once()
        assert response == mock_response_json

# --- Test Non-Retryable Client Errors (4xx) ---
@pytest.mark.parametrize("status_code, error_message_part, expected_exception", [
    (400, "Invalid request (400)", InvalidRequestError),
    (401, "Invalid API key or authentication failure", AuthenticationError),
    (403, "Not authorized to access this resource", AuthorizationError),
    (404, "API request failed with client error 404", InvalidRequestError), 
])
def test_send_analysis_request_non_retryable_client_errors(
    connector_no_retry: XaiGrokConnector, 
    status_code: int, 
    error_message_part: str, 
    expected_exception: Type[Exception]
):
    mock_response = MagicMock(spec=requests.Response)
    mock_response.status_code = status_code
    mock_response.reason = "Client Error"
    mock_response.text = f'{{"error": "Simulated {status_code} error"}}'

    with patch.object(connector_no_retry.session, 'post', return_value=mock_response) as mock_post:
        with pytest.raises(expected_exception) as exc_info:
            connector_no_retry.send_analysis_request(
                transcript_text="Test transcript",
                profile_instructions="Test instructions"
            )
        mock_post.assert_called_once()
        assert error_message_part in str(exc_info.value)

# --- Test Retryable Server Errors (5xx) and Rate Limits (429) ---
@pytest.mark.parametrize("status_code", [
    500, 
    503, 
    429,
])
def test_send_analysis_request_retryable_errors_then_success(
    connector: XaiGrokConnector, 
    status_code: int,
):
    success_response_json = {"choices": [{"message": {"content": '{"summary": "Success after retries"}'}}]}
    
    mock_failure_response = MagicMock(spec=requests.Response)
    mock_failure_response.status_code = status_code
    mock_failure_response.reason = "Retryable Error"
    mock_failure_response.text = f'{{"error": "Simulated {status_code} for retry"}}'

    mock_success_response = MagicMock(spec=requests.Response)
    mock_success_response.status_code = 200
    mock_success_response.reason = "OK"
    mock_success_response.json.return_value = success_response_json
    mock_success_response.text = 'whatever'

    responses = [mock_failure_response, mock_failure_response, mock_success_response]

    with patch.object(connector.session, 'post', side_effect=responses) as mock_post, \
         patch('time.sleep') as mock_sleep:
        response = connector.send_analysis_request(
            transcript_text="Test transcript for retry",
            profile_instructions="Test instructions for retry"
        )
        assert mock_post.call_count == 3
        assert mock_sleep.call_count == 2
        assert response == success_response_json

def test_send_analysis_request_retryable_errors_max_retries_exceeded(
    connector: XaiGrokConnector,
):
    status_code = 503
    # For 503, it becomes a generic APIError after retries if not RateLimitError
    expected_exception_after_retries = APIError if status_code != 429 else RateLimitError 
    error_message_part = f"API request failed with retryable status {status_code}"
    if status_code == 429:
        error_message_part = "Rate limit exceeded (429)"


    mock_failure_responses = [
        MagicMock(spec=requests.Response, status_code=status_code, reason="Server Error", text='{"error":"server busy"}')
    ] * (connector.max_retries + 1)

    with patch.object(connector.session, 'post', side_effect=mock_failure_responses) as mock_post, \
         patch('time.sleep') as mock_sleep:
        with pytest.raises(expected_exception_after_retries) as exc_info:
            connector.send_analysis_request(
                transcript_text="Test transcript for max retries",
                profile_instructions="Test instructions for max retries"
            )
        assert mock_post.call_count == connector.max_retries + 1
        assert mock_sleep.call_count == connector.max_retries
        assert error_message_part in str(exc_info.value)
        assert f"Max retries ({connector.max_retries}) reached" in str(exc_info.value)

# --- Test Network Errors (Timeout, ConnectionError) ---
@pytest.mark.parametrize("network_exception_type", [
    requests.exceptions.Timeout,
    requests.exceptions.ConnectionError,
])
def test_send_analysis_request_network_errors_retry_then_success(
    connector: XaiGrokConnector, 
    network_exception_type: Type[Exception],
):
    success_response_json = {"choices": [{"message": {"content": '{"summary": "Success after network issues"}'}}]}
    mock_success_response = MagicMock(spec=requests.Response, status_code=200, reason="OK", json=lambda: success_response_json, text='ok')

    side_effects = [network_exception_type("Simulated network fail"), mock_success_response]

    with patch.object(connector.session, 'post', side_effect=side_effects) as mock_post, \
         patch('time.sleep') as mock_sleep:
        response = connector.send_analysis_request(
            transcript_text="Test transcript",
            profile_instructions="Test instructions"
        )
        assert mock_post.call_count == 2
        assert mock_sleep.call_count == 1
        assert response == success_response_json

@pytest.mark.parametrize("network_exception_type, expected_final_exception, final_error_message_part", [
    (requests.exceptions.Timeout, ConnectionError, "Request timed out"),
    (requests.exceptions.ConnectionError, ConnectionError, "Connection error"),
])
def test_send_analysis_request_network_errors_persistent_failure(
    connector: XaiGrokConnector,
    network_exception_type: Type[Exception],
    expected_final_exception: Type[Exception],
    final_error_message_part: str
):
    persistent_network_failures = [network_exception_type("Simulated persistent network fail")] * (connector.max_retries + 1)

    with patch.object(connector.session, 'post', side_effect=persistent_network_failures) as mock_post, \
         patch('time.sleep') as mock_sleep:
        with pytest.raises(expected_final_exception) as exc_info:
            connector.send_analysis_request(
                transcript_text="Test transcript",
                profile_instructions="Test instructions"
            )
        assert mock_post.call_count == connector.max_retries + 1
        assert mock_sleep.call_count == connector.max_retries
        assert final_error_message_part in str(exc_info.value)
        assert f"Max retries ({connector.max_retries}) reached" in str(exc_info.value)

# --- Test Backoff Timing (Conceptual) ---
def test_backoff_sleep_times_are_called(connector: XaiGrokConnector):
    status_code = 503
    mock_failure_response = MagicMock(spec=requests.Response, status_code=status_code, reason="Retryable Error", text='err')
    mock_success_response = MagicMock(spec=requests.Response, status_code=200, reason="OK", json=lambda: {"test": "ok"}, text='ok')
    
    responses = [mock_failure_response] * connector.max_retries + [mock_success_response]

    with patch.object(connector.session, 'post', side_effect=responses) as mock_post, \
         patch('time.sleep') as mock_sleep:
        connector.send_analysis_request("text", "instr")
        assert mock_sleep.call_count == connector.max_retries

        if connector.max_retries > 0:
            first_sleep_duration = mock_sleep.call_args_list[0][0][0]
            assert connector.initial_backoff_seconds * 0.5 <= first_sleep_duration <= connector.initial_backoff_seconds * 1.5
        if connector.max_retries > 1:
            second_sleep_duration = mock_sleep.call_args_list[1][0][0]
            expected_second_backoff_base = connector.initial_backoff_seconds * connector.backoff_factor
            assert min(expected_second_backoff_base * 0.5, connector.max_backoff_seconds * 0.5) <= second_sleep_duration 
            assert second_sleep_duration <= min(expected_second_backoff_base * 1.5, connector.max_backoff_seconds * 1.5)

# --- Test Payload Preparation ---
def test_prepare_request_payload_validation(connector: XaiGrokConnector):
    with pytest.raises(InvalidRequestError, match="Transcript text cannot be empty."):
        connector._prepare_request_payload(transcript_text="", profile_instructions="Test")

    payload = connector._prepare_request_payload(transcript_text="Valid text", profile_instructions="")
    assert payload["messages"][0]["content"] == "You are a helpful AI assistant."
    assert payload["messages"][1]["content"] == "Valid text"
