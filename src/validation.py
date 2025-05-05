import re
import json
from typing import List, Dict, Any, Optional
import jsonschema  # Added for schema validation

# --- Import Custom Exceptions ---
from .exceptions import SchemaValidationError
# -----------------------------

class ValidationResult:
    """Stores the results of a validation check."""
    def __init__(self):
        self.is_valid = True
        self.errors: List[Dict[str, str]] = []
        self.warnings: List[Dict[str, str]] = []

    def add_error(self, field: Optional[str], message: str):
        """Add an error to the validation result."""
        self.is_valid = False
        self.errors.append({"field": field or "general", "message": message})

    def add_warning(self, field: Optional[str], message: str):
        """Add a warning to the validation result."""
        self.warnings.append({"field": field or "general", "message": message})

    def merge(self, other_result: 'ValidationResult'):
        """Merge another validation result into this one."""
        if not other_result.is_valid:
            self.is_valid = False
        self.errors.extend(other_result.errors)
        self.warnings.extend(other_result.warnings)

    def __bool__(self) -> bool:
        """Return True if validation passed (no errors), False otherwise."""
        return self.is_valid

    def __str__(self) -> str:
        if self.is_valid:
            return "Validation successful."
        else:
            error_str = "\n".join([f"  - [{e['field']}] {e['message']}" for e in self.errors])
            warning_str = "\n".join([f"  - [{w['field']}] {w['message']}" for w in self.warnings])
            msg = "Validation failed:\n" + error_str
            if self.warnings:
                msg += "\nWarnings:\n" + warning_str
            return msg

# --- Field-Level Validators ---

def validate_profile_name(name: Optional[str], existing_names: List[str] = None, current_id: Optional[str] = None) -> ValidationResult:
    """Validate the profile name."""
    result = ValidationResult()
    if not name:
        result.add_error("name", "Profile name is required.")
        return result

    if not isinstance(name, str):
        result.add_error("name", "Profile name must be a string.")
        return result

    if len(name) < 3 or len(name) > 100:
        result.add_error("name", "Profile name must be between 3 and 100 characters.")

    if not re.match(r"^[a-zA-Z0-9_\-\s]+$", name):
        result.add_error("name", "Profile name can only contain letters, numbers, underscores, hyphens, and spaces.")

    # Check uniqueness if existing_names are provided
    if existing_names:
        # TODO: Need access to the repository/storage to check uniqueness properly,
        # potentially excluding the profile being currently updated (current_id).
        # This placeholder assumes a simple list check.
        if name in existing_names: # This needs refinement for updates
             result.add_error("name", f"Profile name '{name}' already exists.")

    return result

def validate_profile_instructions(instructions: Optional[str]) -> ValidationResult:
    """Validate the profile instructions."""
    result = ValidationResult()
    if instructions is not None:
        if not isinstance(instructions, str):
             result.add_error("instructions", "Instructions must be a string.")
        elif len(instructions) > 10000: # Example limit
             result.add_warning("instructions", "Instructions are very long (over 10000 characters).")
    return result

def validate_schema_definition_basic(schema: Optional[Dict[str, Any]]) -> ValidationResult:
    """Perform basic validation on the schema definition (structure, JSON validity)."""
    result = ValidationResult()
    if schema is None:
        # Allow empty schema for now, specific rules might require it later
        return result

    if not isinstance(schema, dict):
        result.add_error("schema_definition", "Schema definition must be a dictionary (JSON object).")
        return result

    # Check for basic required sections (can be expanded)
    # required_top_level_keys = {'input', 'output'}
    # missing_keys = required_top_level_keys - schema.keys()
    # if missing_keys:
    #     result.add_error("schema_definition", f"Schema definition missing required keys: {', '.join(missing_keys)}.")

    # Attempt to serialize to check JSON validity indirectly (more robust checks later)
    try:
        json.dumps(schema)
    except (TypeError, OverflowError) as e:
        result.add_error("schema_definition", f"Schema definition is not JSON serializable: {str(e)}")

    return result


# --- Structural Schema Validators ---

# Updated validator using jsonschema
def validate_schema_against_standard(schema: Optional[Dict[str, Any]]) -> ValidationResult:
    """Validate the schema definition against the JSON Schema standard."""
    result = ValidationResult()
    if schema is None or not isinstance(schema, dict) or not schema:
        # Allow empty schema definition, but maybe add a warning?
        result.add_warning("schema_definition", "Schema definition is empty or not provided.")
        return result # Considered valid if empty

    try:
        # Validate the schema against the meta-schema (Draft 7 is common)
        # This checks if the schema *itself* is valid according to JSON Schema rules.
        jsonschema.Draft7Validator.check_schema(schema)
        result.add_warning("schema_definition", "Basic JSON Schema structure is valid.") # Use warning for success confirmation?
    except jsonschema.exceptions.SchemaError as e:
        # The schema itself is invalid according to the JSON Schema standard
        result.add_error(
            "schema_definition", 
            f"Invalid JSON Schema structure: {e.message} at path {list(e.path)}"
        )
    except Exception as e:
        # Catch other unexpected errors during validation
        result.add_error("schema_definition", f"Unexpected error during schema validation: {str(e)}")

    # Optional: Add more specific structural checks if needed, 
    #           beyond the standard JSON Schema validation (e.g., ensuring specific top-level keys like 'input', 'output')
    if result.is_valid:
        required_sections = {'input', 'output'} 
        missing_sections = required_sections - set(schema.keys())
        if missing_sections:
             # Add as warning or error depending on strictness
             result.add_warning("schema_definition", f"Schema is missing recommended sections: {missing_sections}")

    return result

def validate_schema_structure(schema: Dict[str, Any]) -> ValidationResult:
    """Validate the deeper structure of the schema definition (DEPRECATED by validate_schema_against_standard)."""
    # This function is now largely superseded by jsonschema validation.
    # Keep for reference or specific non-standard checks if necessary.
    result = ValidationResult()
    result.add_warning("schema_definition", "validate_schema_structure is deprecated; use validate_schema_against_standard.")
    # ... (keep old code commented or remove) ...
    # if not isinstance(schema, dict):
    #     result.add_error(\"schema_definition\", \"Schema definition must be a dictionary.\")
    #     return result
    # 
    # required_sections = {'input', 'output'}
    # actual_sections = set(schema.keys())
    # ... etc ...
    return result


# --- Sanitization ---

def sanitize_string(input_str: Optional[str]) -> Optional[str]:
    """Basic sanitization for string inputs (e.g., escape HTML)."""
    if input_str is None:
        return None
    # Example: Basic HTML escaping. More robust sanitization might be needed.
    import html
    return html.escape(input_str)

# --- Profile Validation Orchestrator ---

# Placeholder - This will likely live in the Profile or Repository class
# def validate_analysis_profile(profile_data: Dict[str, Any], existing_names: List[str] = None) -> ValidationResult:
#     """Run all validations for an Analysis Profile."""
#     full_result = ValidationResult()
#
#     # Field validations
#     full_result.merge(validate_profile_name(profile_data.get('name'), existing_names))
#     full_result.merge(validate_profile_instructions(profile_data.get('instructions')))
#     basic_schema_result = validate_schema_definition_basic(profile_data.get('schema_definition'))
#     full_result.merge(basic_schema_result)
#
#     # Structural schema validation (only if basic validation passed)
#     if basic_schema_result.is_valid and isinstance(profile_data.get('schema_definition'), dict):
#         full_result.merge(validate_schema_structure(profile_data['schema_definition']))
#
#     # TODO: Add business rule validations
#
#     return full_result 