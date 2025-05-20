import unittest
import json
from unittest.mock import patch, MagicMock

# Assuming src is in PYTHONPATH or correctly pathed for imports
from src.core.response_parser import (
    parse_analysis_response,
    sanitize_response_data,
    recover_partial_response,
    handle_response_errors,
    detect_malformed_response,
    ANALYSIS_SCHEMAS, # Import for use in tests
    ResponseParsingError,
    ResponseValidationError
)
from src.core import response_parser # To mock internal functions like _parse_text_response

# Example Schemas (can be expanded or mocked)
# Add a schema for a new type for testing
ANALYSIS_SCHEMAS['test_type_with_schema'] = {
    "type": "object",
    "properties": {
        "key": {"type": "string"},
        "value": {"type": "number"}
    },
    "required": ["key", "value"]
}
ANALYSIS_SCHEMAS['summary_text'] = { # For testing _parse_text_response through parse_analysis_response
    "type": "object",
    "properties": {"summary": {"type": "string"}},
    "required": ["summary"]
}


class TestResponseParser(unittest.TestCase):

    def test_parse_valid_json_with_schema(self):
        raw_response = {
            "choices": [{"message": {"content": json.dumps({"key": "test", "value": 123})}}]
        }
        result = parse_analysis_response(raw_response, 'test_type_with_schema')
        self.assertEqual(result, {"key": "test", "value": 123})

    def test_parse_valid_json_direct_content_with_schema(self):
        # Content is already the JSON, not a string needing json.loads()
        raw_response = {
            "choices": [{"message": {"content": {"key": "test", "value": 123}}}]
        }
        result = parse_analysis_response(raw_response, 'test_type_with_schema')
        self.assertEqual(result, {"key": "test", "value": 123})

    def test_parse_valid_json_no_schema(self):
        raw_response = {
            "choices": [{"message": {"content": json.dumps({"data": "any"})}}]
        }
        result = parse_analysis_response(raw_response, 'type_without_schema')
        self.assertEqual(result, {"data": "any"}) # Should parse and transform (if any rule)

    def test_parse_json_fails_schema_validation(self):
        raw_response = {
            "choices": [{"message": {"content": json.dumps({"key": "test", "wrong_value_type": "123"})}}]
        }
        with self.assertRaises(ResponseValidationError):
            parse_analysis_response(raw_response, 'test_type_with_schema')

    @patch('src.core.response_parser._parse_text_response')
    def test_parse_non_json_content_calls_parse_text_response(self, mock_parse_text):
        mock_parse_text.return_value = {"parsed_text": "content"}
        raw_response = {
            "choices": [{"message": {"content": "This is plain text"}}]
        }
        # Temporarily remove schema that would cause it to try to validate text as JSON object
        original_schema = ANALYSIS_SCHEMAS.pop('text_type', None)
        
        result = parse_analysis_response(raw_response, 'text_type')
        mock_parse_text.assert_called_once_with("This is plain text", 'text_type')
        self.assertEqual(result, {"parsed_text": "content"})

        if original_schema: # Restore if it was popped
            ANALYSIS_SCHEMAS['text_type'] = original_schema


    def test_parse_direct_json_string_input(self):
        # Raw response itself is a JSON string
        raw_response_str = json.dumps({"key": "direct", "value": 456})
        # This scenario implies the outer layers didn't wrap it in the Grok structure
        # parse_analysis_response should handle this if it's not wrapped in "choices"
        # by attempting json.loads on the string, then if it fails, wrap it for Grok path.
        # Current logic: if raw_response is string and json.loads fails, it assumes it's the content itself for Grok.
        # Let's test the case where raw_response_str IS the JSON payload.
        
        # Mocking the schema to avoid validation issues if keys don't match.
        # The goal is to test if it correctly parses the direct string.
        with patch.dict(ANALYSIS_SCHEMAS, {'direct_type': {"type": "object", "properties": {"key": {"type": "string"}, "value": {"type": "number"}}}}):
            result = parse_analysis_response(raw_response_str, 'direct_type')
            self.assertEqual(result, {"key": "direct", "value": 456})


    def test_parse_malformed_json_string_content(self):
        raw_response = {
            "choices": [{'message': {'content': '{"key": "test", "value": 123'}}] # Missing closing brace
        }
        # Expecting a ResponseValidationError because _parse_text_response will likely return
        # something that doesn't match 'test_type_with_schema', leading to schema validation failure.
        with self.assertRaises(ResponseValidationError) as cm:
            parse_analysis_response(raw_response, 'test_type_with_schema')
        # Check if the error message or type indicates it tried text parsing or failed JSON
        # Based on current logic, json.loads(content_str) fails, then _parse_text_response is called.
        # If _parse_text_response returns something that then fails schema validation, it'd be a ResponseValidationError.
        # If _parse_text_response itself is simple, it's more about what it returns.
        # For this test, let's assume schema validation for 'test_type_with_schema' will fail if _parse_text_response returns simple text.
        self.assertIn("Schema validation failed for 'test_type_with_schema'", str(cm.exception))
        self.assertIn("'key' is a required property", str(cm.exception))


    def test_parse_response_missing_grok_structure(self):
        # Raw response is a dict but not the expected Grok structure
        # It should assume the raw_response itself is the content to be parsed.
        raw_response_direct_content = {"key": "direct_struct", "value": 789}
        with patch.dict(ANALYSIS_SCHEMAS, {'direct_struct_type': {"type": "object", "properties": {"key": {"type": "string"}, "value": {"type": "number"}}}}):
            result = parse_analysis_response(raw_response_direct_content, 'direct_struct_type')
            self.assertEqual(result, {"key": "direct_struct", "value": 789})

    @patch('src.core.response_parser._transform_response')
    def test_transform_response_integration(self, mock_transform):
        mock_transform.return_value = {"transformed": True}
        raw_response = {
            "choices": [{"message": {"content": json.dumps({"key": "data"})}}]
        }
        result = parse_analysis_response(raw_response, 'some_type')
        # mock_transform is called with the result of json.loads or _parse_text_response
        mock_transform.assert_called_once_with({"key": "data"}, 'some_type')
        self.assertEqual(result, {"transformed": True})

    def test_sanitize_response_data(self):
        data_to_sanitize = {
            "htmlTag": "<script>alert('xss')</script>",
            "normalText": "Hello World",
            "nested": {"anotherTag": "<b>bold</b>"},
            "listValue": ["<p>para</p>", 123]
        }
        sanitized = sanitize_response_data(data_to_sanitize)
        self.assertEqual(sanitized['html_tag'], "&lt;script&gt;alert(&#x27;xss&#x27;)&lt;/script&gt;")
        self.assertEqual(sanitized['normal_text'], "Hello World")
        self.assertEqual(sanitized['nested']['another_tag'], "&lt;b&gt;bold&lt;/b&gt;")
        self.assertEqual(sanitized['list_value'][0], "&lt;p&gt;para&lt;/p&gt;")
        self.assertEqual(sanitized['list_value'][1], 123)
        self.assertNotIn("htmlTag", sanitized) # Key should be snake_case

    def test_recover_partial_response_valid_json_in_text(self):
        text_with_json = 'Some text before a valid json object {"key": "partial", "value": 10} and some text after.'
        recovered = recover_partial_response(text_with_json, "test_type_with_schema")
        self.assertIn("recovered_data", recovered)
        self.assertEqual(recovered["recovered_data"], {"key": "partial", "value": 10})

    def test_recover_partial_response_no_json(self):
        text_without_json = "This is just plain text without any json."
        recovered = recover_partial_response(text_without_json, "test_type_with_schema")
        self.assertEqual(recovered, {})

    def test_handle_response_errors_success(self):
        raw_response = {
            "choices": [{"message": {"content": json.dumps({"key": "test", "value": 123})}}]
        }
        success, result = handle_response_errors(raw_response, 'test_type_with_schema')
        self.assertTrue(success)
        self.assertEqual(result, {"key": "test", "value": 123})

    @patch('src.core.response_parser.recover_partial_response')
    def test_handle_response_errors_parsing_error_with_recovery(self, mock_recover):
        mock_recover.return_value = {"recovered_data": {"partial": "content"}, "recovery_notes": "Recovered"}
        raw_response_malformed_content = { # Content string will fail json.loads
            "choices": [{'message': {'content': '{"key": "test", "value": 123'}}] 
        }
        # This will cause parse_analysis_response to call _parse_text_response, 
        # which might then fail schema validation if schema is strict for 'test_type_with_schema'
        # Let's use a type that would definitely fail schema if text is returned
        
        success, result = handle_response_errors(raw_response_malformed_content, 'test_type_with_schema')
        self.assertFalse(success)
        self.assertEqual(result.get("status"), "partial_recovery")
        self.assertIn("partial_data", result)
        self.assertEqual(result["partial_data"], {"partial": "content"})
        mock_recover.assert_called_once()

    @patch('src.core.response_parser.recover_partial_response')
    def test_handle_response_errors_parsing_error_no_recovery(self, mock_recover):
        mock_recover.return_value = {} # No recovery
        raw_response_malformed_content = {
            "choices": [{'message': {'content': '{"key": "test", "value": 123'}}]
        }
        success, result = handle_response_errors(raw_response_malformed_content, 'test_type_with_schema')
        self.assertFalse(success)
        self.assertEqual(result.get("status"), "processing_failed") # or validation_failed depending on path
        self.assertNotIn("partial_data", result)
        mock_recover.assert_called_once()

    def test_detect_malformed_response_empty(self):
        is_malformed, reason = detect_malformed_response("")
        self.assertTrue(is_malformed)
        self.assertEqual(reason, "Empty response data")

    def test_detect_malformed_response_truncated_json(self):
        is_malformed, reason = detect_malformed_response('{"key": "value"')
        self.assertTrue(is_malformed)
        self.assertEqual(reason, "Truncated JSON structure (more open braces than close)")

    def test_detect_malformed_response_error_pattern(self):
        is_malformed, reason = detect_malformed_response("I'm sorry, I cannot fulfill this request.")
        self.assertTrue(is_malformed)
        self.assertIn("potential error indicator", reason)
        
    def test_detect_malformed_response_valid_text_with_error_pattern_ignored(self):
        # Longer text that happens to contain "I'm sorry" but is not an error message
        long_text = "This is a long transcript where the user said 'I'm sorry for the delay' and then continued with the main topic which is about project X, Y, and Z. The content is perfectly valid."
        is_malformed, reason = detect_malformed_response(long_text)
        self.assertFalse(is_malformed) # Heuristic should ignore this

    def test_detect_malformed_response_valid_json(self):
        is_malformed, reason = detect_malformed_response({"key": "value"})
        self.assertFalse(is_malformed)
        self.assertIsNone(reason)

if __name__ == '__main__':
    unittest.main() 