import json
import jsonschema
import logging
import html
import re
from datetime import datetime # Added for log_response_processing

from src.core.exceptions import ResponseParsingError, ResponseValidationError

logger = logging.getLogger(__name__)

# Placeholder for schema registry
ANALYSIS_SCHEMAS = {
    "default_schema": {
        "type": "object",
        "properties": {
            "summary": {"type": "string"},
            "key_topics": {"type": "array", "items": {"type": "string"}},
            "sentiment": {"type": "string", "enum": ["positive", "neutral", "negative"]}
        },
        "required": ["summary", "key_topics"]
    },
    "sentiment": { # Added example from previous log
        "type": "object",
        "required": ["sentiment", "confidence", "explanation"],
        "properties": {
            "sentiment": {"type": "string", "enum": ["positive", "negative", "neutral"]},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "explanation": {"type": "string"},
            "key_phrases": {"type": "array", "items": {"type": "string"}}
        }
    }
    # Schemas would be dynamically populated or managed elsewhere in a real system
}

# Placeholder for analysis schemas - this would be more robust in a real app
# (e.g., loaded from files, a database, or a dedicated schema registry module)
SENTIMENT_ANALYSIS_SCHEMA = {
    "type": "object",
    # Add other analysis types as needed
}

# Helper function to parse non-JSON text responses
def _parse_text_response(text_content: str, analysis_type: str) -> dict:
    logger.debug(f"Parsing text response for analysis_type: {analysis_type}")
    # Example: if analysis_type is "summary_text", extract key points
    if analysis_type == "summary_text":
        return {"summary": text_content.strip()}
    # Fallback for unknown text types
    return {"raw_text_content": text_content}

# Helper function to transform parsed data
def _transform_response(parsed_data: dict, analysis_type: str) -> dict:
    logger.debug(f"Transforming response for analysis_type: {analysis_type}")
    # Example: if analysis_type is "sentiment", ensure specific fields exist
    if analysis_type == "sentiment" and isinstance(parsed_data, dict):
        return {
            "sentiment_value": parsed_data.get("sentiment"),
            "confidence_score": parsed_data.get("confidence"),
            "details": parsed_data.get("explanation"),
            "mentioned_phrases": parsed_data.get("key_phrases", [])
        }
    # Return data as is if no specific transformation or if not a dict
    return parsed_data

def parse_analysis_response(raw_response: str | dict, analysis_type: str = "default_schema") -> dict:
    logger.debug(f"Attempting to parse raw_response for analysis_type: {analysis_type}")
    try:
        data_source = raw_response
        if isinstance(raw_response, str):
            try:
                # First, assume raw_response string IS the direct JSON payload
                data_source = json.loads(raw_response)
            except json.JSONDecodeError:
                # If that fails, assume it's a full API response where content needs extraction
                # This is a common pattern if an outer layer didn't pre-parse
                data_source = {"choices": [{"message": {"content": raw_response}}]}

        if not isinstance(data_source, dict):
             raise ResponseParsingError(f"Unexpected data_source type after initial processing: {type(data_source)}")

        content_to_parse: dict | str
        # Standard LLM response structure:
        if "choices" in data_source and isinstance(data_source["choices"], list) and len(data_source["choices"]) > 0:
            first_choice = data_source["choices"][0]
            if "message" in first_choice and isinstance(first_choice["message"], dict) and "content" in first_choice["message"]:
                content_to_parse = first_choice["message"]["content"]
            else:
                raise ResponseParsingError("API response structure missing 'message.content' in first choice.")
        else:
            # Fallback: if not the above structure, assume data_source IS the content to parse.
            # This allows flexibility if the input `raw_response` is already the direct data.
            logger.warning("Response does not match typical 'choices[0].message.content' structure. Assuming input is the direct content.")
            content_to_parse = data_source # type: ignore

        parsed_content: dict
        if isinstance(content_to_parse, str):
            try:
                parsed_content = json.loads(content_to_parse)
            except json.JSONDecodeError:
                logger.warning(f"Content string is not JSON. Attempting text parsing for '{analysis_type}'.")
                parsed_content = _parse_text_response(content_to_parse, analysis_type)
        elif isinstance(content_to_parse, dict):
            parsed_content = content_to_parse # Already a dictionary
        else:
            raise ResponseParsingError(f"Content to parse is neither string nor dict: {type(content_to_parse)}")

        schema = ANALYSIS_SCHEMAS.get(analysis_type)
        if schema:
            jsonschema.validate(instance=parsed_content, schema=schema)
            logger.info(f"Response for '{analysis_type}' validated successfully against schema.")
        else:
            logger.warning(f"No schema found for analysis_type: '{analysis_type}'. Skipping schema validation.")

        transformed_data = _transform_response(parsed_content, analysis_type)
        logger.debug(f"Successfully parsed and transformed response for analysis_type: {analysis_type}")
        return transformed_data

    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON format in response string: {e}", exc_info=True)
        raise ResponseParsingError(f"Invalid JSON format: {e}") from e
    except jsonschema.exceptions.ValidationError as e:
        logger.error(f"Response schema validation failed for '{analysis_type}': {e.message}", exc_info=True)
        raise ResponseValidationError(f"Schema validation failed for '{analysis_type}': {e.message}") from e
    except ResponseParsingError as e:
        logger.error(f"Response parsing error: {e}", exc_info=True)
        raise
    except Exception as e:
        logger.error(f"Unexpected error during response parsing for '{analysis_type}': {e}", exc_info=True)
        raise ResponseParsingError(f"Unexpected parsing error: {e}") from e

def _sanitize_value(value):
    if isinstance(value, str):
        return html.escape(value)
    if isinstance(value, list):
        return [_sanitize_value(item) for item in value]
    if isinstance(value, dict):
        return sanitize_response_data(value) # Recursive call for nested dicts
    return value

def sanitize_response_data(data: dict) -> dict:
    if not isinstance(data, dict):
        logger.warning(f"Sanitization input is not a dict: {type(data)}. Returning as is.")
        return data 
        
    sanitized = {}
    for key, value in data.items():
        snake_case_key = re.sub(r'(?<!^)(?=[A-Z])', '_', str(key)).lower() # Ensure key is string
        snake_case_key = re.sub(r'[\\W_]+', '_', snake_case_key).strip('_')
        if not snake_case_key:
            snake_case_key = f"sanitized_key_{str(key).lower()}"
        sanitized[snake_case_key] = _sanitize_value(value)
    return sanitized

# Restoring original implementations from logs
def recover_partial_response(raw_response: str | dict, analysis_type: str) -> dict:
    logger.debug(f"Attempting to recover partial response for analysis_type: {analysis_type}")
    try:
        response_str = raw_response if isinstance(raw_response, str) else json.dumps(raw_response)
        
        logger.debug(f"Attempting to recover partial JSON from: {response_str[:200]}...")
        try:
            if isinstance(response_str, str):
                # Simpler regex to find potential JSON objects (non-greedy)
                # This will find basic, non-nested objects. A more robust parser would be needed for complex cases.
                json_pattern = r'(\{.*?\})' # Changed from r'\{(?:[^{}]|(?R))*\}'
                potential_jsons = re.findall(json_pattern, response_str)
                
                for potential_json_str in potential_jsons:
                    try:
                        data = json.loads(potential_json_str)
                        # Basic check: does it have any keys?
                        if isinstance(data, dict) and data:
                            schema = ANALYSIS_SCHEMAS.get(analysis_type, {})
                            required_keys = schema.get("required", [])
                            
                            # Check if some expected keys are present (heuristic)
                            if not required_keys or any(key in data for key in required_keys):
                                logger.info(f"Partially recovered data: {data}")
                                return {
                                    "recovered_data": data,
                                    "is_complete": False, # Assume not complete
                                    "recovery_notes": "Recovered a JSON-like structure from the response."
                                }
                    except json.JSONDecodeError:
                        continue # Not a valid JSON, try next match
                
            logger.warning("Could not recover partial JSON data.")
            return {}
        except Exception as e:
            logger.error(f"Error during partial recovery: {e}", exc_info=True)
            return {}
    except Exception as e:
        logger.error(f"Error during partial recovery: {e}", exc_info=True)
        return {}

def handle_response_errors(raw_response: str | dict, analysis_type: str, job_id=None, ext_logger=None):
    current_logger = ext_logger or logger # Use external logger if provided
    current_logger.debug(f"Handling response errors for job_id: {job_id}, analysis_type: {analysis_type}")
    try:
        result = parse_analysis_response(raw_response, analysis_type)
        return True, result
    except (ResponseParsingError, ResponseValidationError) as e:
        current_logger.error(f"Processing error for job {job_id} ({analysis_type}): {e}")
        
        # Attempt recovery
        recovered_data = recover_partial_response(raw_response, analysis_type)
        if recovered_data and "recovered_data" in recovered_data:
            current_logger.warning(f"Partially recovered data for job {job_id}")
            return False, { # Indicate failure but provide partial data
                "partial_data": recovered_data["recovered_data"],
                "error": str(e),
                "status": "partial_recovery"
            }
        
        return False, {"error": str(e), "status": "processing_failed"}
    except Exception as e: # Catch any other unexpected errors
        current_logger.error(f"Unexpected critical error processing response for job {job_id}: {e}", exc_info=True)
        return False, {"error": f"Unexpected critical error: {e}", "status": "critical_failure"}


def detect_malformed_response(response_data: str | dict) -> tuple[bool, str | None]:
    logger.debug("Detecting malformed response.")
    if not response_data:
        return True, "Empty response data"
        
    response_str = response_data if isinstance(response_data, str) else json.dumps(response_data)

    # Check for truncated JSON (common with token limits)
    if response_str.count('{') > response_str.count('}'): # Basic check for open braces
        return True, "Truncated JSON structure (more open braces than close)"
    if response_str.count('[') > response_str.count(']'): # Basic check for open brackets
        return True, "Truncated JSON structure (more open brackets than close)"
        
    # Check for common error patterns in LLM responses
    error_patterns = [
        "i'm sorry", "i apologize", "i cannot", "as an ai",
        "error", "unable to", "failed to", "not possible"
    ]
    
    lower_response = response_str.lower()
    for pattern in error_patterns:
        if pattern in lower_response:
            # Ensure it's not part of a valid analysis, e.g. analyzing text that contains "I'm sorry"
            # This is a heuristic and might need refinement
            if len(lower_response) < 200 and "content" not in lower_response : # Short error messages are more likely to be actual errors
                 return True, f"Response contains potential error indicator: '{pattern}'"
                
    return False, None

def log_response_processing(job_id, analysis_type, raw_response, parsed_result_or_error, success, ext_logger=None):
    current_logger = ext_logger or logger
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "job_id": job_id,
        "analysis_type": analysis_type,
        "success": success,
        "response_size": len(str(raw_response)),
    }
    
    if success:
        # For successful parsing, summarize the result keys
        if isinstance(parsed_result_or_error, dict):
            log_entry["result_summary_keys"] = list(parsed_result_or_error.keys())
        else:
            log_entry["result_summary"] = str(parsed_result_or_error)[:200] + "..." # Truncate
    else: # Error case
        if isinstance(parsed_result_or_error, dict):
            log_entry["error_details"] = parsed_result_or_error.get("error", "Unknown error")
            log_entry["error_status"] = parsed_result_or_error.get("status", "unknown_error_status")
            if "partial_data" in parsed_result_or_error and isinstance(parsed_result_or_error["partial_data"], dict):
                 log_entry["partial_data_summary_keys"] = list(parsed_result_or_error["partial_data"].keys())
        else:
            log_entry["error_details"] = str(parsed_result_or_error)

    current_logger.info(f"Response processing log: {json.dumps(log_entry)}")
    # In a real system, this might write to a structured log store or monitoring system
    # e.g., ResponseProcessingLogDB.create(**log_entry) 