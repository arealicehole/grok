def format_api_error(status_code, error_message, endpoint=None):
    """Formats API error details into a user-friendly string."""
    title = f"API Error (Code: {status_code})"
    message = f"Message: {error_message}"
    if endpoint:
        message += f"\nEndpoint: {endpoint}"
    return title, message

def format_parsing_error(error_type, details, file_source=None):
    """Formats parsing error details."""
    title = f"Parsing Error ({error_type})"
    message = f"Details: {details}"
    if file_source:
        message += f"\nSource: {file_source}"
    return title, message

def format_large_output_error(output_size_kb, limit_kb, content_type="JSON"):
    """Formats errors for large output that was truncated."""
    title = f"Large {content_type} Output"
    message = (
        f"The {content_type.lower()} output ({output_size_kb:.2f} KB) exceeds the display limit ({limit_kb:.2f} KB) "
        f"and has been truncated.\n\n"
        f"You can use the 'View Full Output' option to see the complete content."
    )
    return title, message

def format_generic_error(custom_title, custom_message):
    """Formats a generic error message."""
    return custom_title, custom_message

# Example Usage (can be removed or kept for testing)
if __name__ == '__main__':
    api_title, api_msg = format_api_error(500, "Internal Server Error", "/analyze")
    print(f"{api_title}\n{api_msg}\n")

    parse_title, parse_msg = format_parsing_error("JSONDecodeError", "Unexpected token '}' at position 123", "results.json")
    print(f"{parse_title}\n{parse_msg}\n")

    large_title, large_msg = format_large_output_error(1500.50, 1000.0)
    print(f"{large_title}\n{large_msg}\n")

    generic_title, generic_msg = format_generic_error("File Access Denied", "Could not read the specified file due to permission issues.")
    print(f"{generic_title}\n{generic_msg}") 