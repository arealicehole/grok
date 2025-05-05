import uuid
import copy
import deepdiff
from datetime import datetime
from typing import List, Dict, Optional, Tuple, Any

# Placeholder for actual model and storage implementation
# Assume these exist and provide the necessary interface
from .analysis_profile import AnalysisProfile # Assuming model is in src/analysis_profile.py
# Assume storage functions exist (e.g., in src/profile_storage.py)
from .profile_storage import load_profile, save_profile, list_all_profiles, profile_exists, _profiles_db

def clone_profile(source_id_or_name: str, new_name: str = None, modifications: dict = None) -> AnalysisProfile:
    """
    Creates a copy of an existing profile with optional modifications.

    Args:
        source_id_or_name: ID or Name of the profile to clone.
        new_name: Optional new name (defaults to "Copy of [original name]").
        modifications: Dictionary of attributes to modify in the new profile.

    Returns:
        The newly created and saved profile.

    Raises:
        ValueError: If the source profile is not found or if the new_name conflicts.
    """
    source = load_profile(source_id_or_name)
    if not source:
        raise ValueError(f"Source profile '{source_id_or_name}' not found.")

    target_name = new_name or f"Copy of {source.name}"

    # Check for name conflict before proceeding
    if profile_exists(target_name):
        raise ValueError(f"A profile with the name '{target_name}' already exists.")

    # Deep copy to avoid reference issues with nested objects like schema_definition
    new_profile = copy.deepcopy(source)
    new_profile.id = uuid.uuid4() # Generate a new unique ID
    new_profile.name = target_name
    new_profile.created_at = datetime.utcnow()
    new_profile.updated_at = new_profile.created_at

    # Apply any modifications
    if modifications:
        for key, value in modifications.items():
            # Ensure we only modify existing attributes of the AnalysisProfile model
            if hasattr(new_profile, key):
                setattr(new_profile, key, value)
                new_profile.updated_at = datetime.utcnow() # Update timestamp if modified

    # Save the newly created profile
    save_profile(new_profile)
    return new_profile

def create_template_profile(template_type: str, name: str = None) -> AnalysisProfile:
    """
    Creates a pre-configured profile based on common use cases.

    Args:
        template_type: The type of template ('basic', 'detailed', etc.).
        name: Optional name for the new profile.

    Returns:
        The newly created and saved template profile.

    Raises:
        ValueError: If the template type is unknown or the name conflicts.
    """
    templates = {
        "basic": {
            "name": "Basic Analysis Template",
            "schema_definition": {
                "inputs": {"transcript": {"type": "text", "description": "Full conversation transcript"}},
                "outputs": {
                    "summary": {"type": "text", "description": "Concise summary of the conversation"},
                    "key_points": {"type": "list", "description": "Bullet points of key topics discussed"}
                }
            },
            "instructions": "Analyze the provided transcript. Generate a concise summary and list the key points discussed."
        },
        "detailed": {
            "name": "Detailed Analysis Template",
             "schema_definition": {
                "inputs": {"transcript": {"type": "text", "description": "Full conversation transcript"}},
                "outputs": {
                    "summary": {"type": "text", "description": "Detailed summary"},
                    "topics": {"type": "list", "description": "Main topics"},
                    "action_items": {"type": "list", "description": "Actionable items identified"},
                    "sentiment": {"type": "string", "description": "Overall sentiment (Positive/Negative/Neutral)"}
                }
            },
            "instructions": "Perform a detailed analysis: summarize, list topics, extract action items, and determine sentiment."
        }
        # Add more templates as needed (e.g., 'security', 'performance')
    }

    if template_type not in templates:
        raise ValueError(f"Unknown template type: '{template_type}'. Available types: {', '.join(templates.keys())}")

    template_config = templates[template_type]
    profile_name = name or template_config["name"]

    # Check for name conflict
    if profile_exists(profile_name):
        raise ValueError(f"A profile with the name '{profile_name}' already exists.")

    profile = AnalysisProfile(
        name=profile_name,
        schema_definition=template_config["schema_definition"],
        instructions=template_config["instructions"]
    )

    save_profile(profile)
    return profile

def diff_profiles(profile1_id_or_name: str, profile2_id_or_name: str) -> dict:
    """
    Compares two profiles and returns their differences using deepdiff.

    Args:
        profile1_id_or_name: ID or Name of the first profile.
        profile2_id_or_name: ID or Name of the second profile.

    Returns:
        A dictionary representing the differences, as returned by deepdiff.
        Excludes metadata fields (id, created_at, updated_at) from comparison.

    Raises:
        ValueError: If either profile is not found.
    """
    profile1 = load_profile(profile1_id_or_name)
    profile2 = load_profile(profile2_id_or_name)

    if not profile1:
        raise ValueError(f"Profile '{profile1_id_or_name}' not found.")
    if not profile2:
        raise ValueError(f"Profile '{profile2_id_or_name}' not found.")

    # Convert to dictionaries, excluding metadata fields for comparison
    exclude_paths = ["root['id']", "root['created_at']", "root['updated_at']"]
    dict1 = profile1.to_dict()
    dict2 = profile2.to_dict()

    # Use DeepDiff for comprehensive comparison
    diff = deepdiff.DeepDiff(dict1, dict2, ignore_order=True, exclude_paths=exclude_paths)

    return diff.to_dict() # Return diff as a standard dictionary

def search_profiles_by_text(query: str, search_fields: Optional[List[str]] = None) -> List[AnalysisProfile]:
    """
    Performs a simple case-insensitive text search across profile fields.

    Args:
        query: Text to search for.
        search_fields: List of fields to search (defaults to ['name', 'instructions']).
                       Can include nested fields in schema_definition using dot notation
                       (e.g., 'schema_definition.inputs.transcript.description').

    Returns:
        List of matching profiles.
    """
    if search_fields is None:
        search_fields = ['name', 'instructions']

    all_profiles = list_all_profiles()
    matching_profiles = []
    query_lower = query.lower()

    for profile in all_profiles:
        profile_dict = profile.to_dict()
        found = False
        for field_path in search_fields:
            try:
                # Simple dot notation traversal for nested fields
                value = profile_dict
                parts = field_path.split('.')
                for part in parts:
                    if isinstance(value, dict):
                        value = value.get(part)
                    else:
                        value = None # Path doesn't exist fully
                        break

                if value and isinstance(value, str):
                    if query_lower in value.lower():
                        found = True
                        break
                # Could extend to search lists of strings etc.
            except Exception:
                # Ignore errors during traversal (e.g., field not present)
                continue
        if found:
            matching_profiles.append(profile)

    return matching_profiles

def validate_schema_compatibility(schema1: dict, schema2: dict) -> Tuple[bool, List[str]]:
    """
    Checks if two schemas are compatible for data exchange or merging.
    NOTE: This is a basic compatibility check. More sophisticated checks
          might be needed depending on specific use cases.

    Args:
        schema1: The first schema dictionary.
        schema2: The second schema dictionary.

    Returns:
        Tuple containing (is_compatible: bool, list_of_incompatibilities: List[str])
    """
    incompatibilities = []

    # --- Basic Structural Checks ---
    if not isinstance(schema1, dict) or not isinstance(schema2, dict):
        return False, ["One or both inputs are not valid schema dictionaries."]

    # --- Version Check (Optional but recommended) ---
    # Assuming schemas might have a 'version' key
    v1 = schema1.get("version")
    v2 = schema2.get("version")
    if v1 and v2 and v1 != v2:
        incompatibilities.append(f"Schema version mismatch: '{v1}' vs '{v2}'.")
        # Depending on strictness, might return False here

    # --- Input Field Compatibility ---
    inputs1 = schema1.get("inputs", {})
    inputs2 = schema2.get("inputs", {})
    if not isinstance(inputs1, dict) or not isinstance(inputs2, dict):
        return False, ["Schema 'inputs' sections must be dictionaries."]

    for name, props1 in inputs1.items():
        if name not in inputs2:
            # If an input field from schema1 is missing in schema2, it *might* be an incompatibility
            # depending on how the schemas are used. For merging, this might be acceptable.
            # For data validation, it might be critical. Let's note it as a potential issue.
            incompatibilities.append(f"Input field '{name}' exists in schema1 but not in schema2.")
        else:
            props2 = inputs2[name]
            # Check type compatibility (simple exact match for now)
            type1 = props1.get("type")
            type2 = props2.get("type")
            if type1 and type2 and type1 != type2:
                incompatibilities.append(f"Type mismatch for input field '{name}': '{type1}' vs '{type2}'.")
            # Could add more checks: required status, descriptions, etc.

    # --- Output Field Compatibility (Similar logic, potentially less strict) ---
    outputs1 = schema1.get("outputs", {})
    outputs2 = schema2.get("outputs", {})
    if not isinstance(outputs1, dict) or not isinstance(outputs2, dict):
        return False, ["Schema 'outputs' sections must be dictionaries."]

    for name, props1 in outputs1.items():
        if name in outputs2:
            props2 = outputs2[name]
            type1 = props1.get("type")
            type2 = props2.get("type")
            if type1 and type2 and type1 != type2:
                # Type mismatches in outputs might be less critical than inputs
                incompatibilities.append(f"Type mismatch for output field '{name}': '{type1}' vs '{type2}'.")

    # Consider a schema compatible if there are no critical incompatibilities (like type mismatches)
    # The presence/absence of fields might be handled by the merging logic itself.
    is_compatible = not any("mismatch" in issue for issue in incompatibilities)

    return is_compatible, incompatibilities

def merge_profiles(
    profile_ids_or_names: List[str],
    new_name: str,
    merge_strategy: str = 'primary'
) -> AnalysisProfile:
    """
    Combines elements from multiple profiles into a new profile.

    Args:
        profile_ids_or_names: List of profile IDs or Names to merge (at least two).
        new_name: Name for the merged profile.
        merge_strategy: How to handle conflicts ('primary', 'union', 'intersection').
                        Currently, only 'primary' is fully implemented.

    Returns:
        The newly created merged profile.

    Raises:
        ValueError: If less than two profiles are provided, a profile is not found,
                    the new name conflicts, or an unsupported merge strategy is used.
    """
    if len(profile_ids_or_names) < 2:
        raise ValueError("At least two profiles are required for merging.")

    # Check for new name conflict first
    if profile_exists(new_name):
        raise ValueError(f"A profile with the name '{new_name}' already exists.")

    profiles = []
    for pid_or_name in profile_ids_or_names:
        profile = load_profile(pid_or_name)
        if not profile:
            raise ValueError(f"Profile '{pid_or_name}' not found.")
        profiles.append(profile)

    # Create new profile with basic metadata
    merged_profile = AnalysisProfile(
        name=new_name
        # ID, created_at, updated_at are handled by AnalysisProfile constructor/save
    )

    # Merge instructions (concatenate with headers)
    merged_profile.instructions = "\n\n---\n\n".join([
        f"## Instructions from Profile: '{p.name}' (ID: {p.id})\n\n{p.instructions}"
        for p in profiles if p.instructions # Only include if instructions exist
    ])

    # --- Merge schema definitions based on strategy ---
    primary_profile = profiles[0]

    if merge_strategy == 'primary':
        # Use the first profile's schema as the base
        merged_profile.schema_definition = copy.deepcopy(primary_profile.schema_definition)

        # Add missing fields from subsequent profiles (simple merge)
        # Note: This doesn't handle conflicting definitions for the *same* field name.
        # It just adds fields present in others but missing in the primary.
        for other_profile in profiles[1:]:
            # Merge inputs
            if "inputs" in other_profile.schema_definition:
                for input_name, input_props in other_profile.schema_definition["inputs"].items():
                    if input_name not in merged_profile.schema_definition.get("inputs", {}):
                        if "inputs" not in merged_profile.schema_definition:
                             merged_profile.schema_definition["inputs"] = {}
                        merged_profile.schema_definition["inputs"][input_name] = copy.deepcopy(input_props)
            # Merge outputs
            if "outputs" in other_profile.schema_definition:
                for output_name, output_props in other_profile.schema_definition["outputs"].items():
                    if output_name not in merged_profile.schema_definition.get("outputs", {}):
                         if "outputs" not in merged_profile.schema_definition:
                             merged_profile.schema_definition["outputs"] = {}
                         merged_profile.schema_definition["outputs"][output_name] = copy.deepcopy(output_props)

    elif merge_strategy == 'union':
        # TODO: Implement schema union logic (more complex)
        # - Combine all fields from all profiles.
        # - Need rules for handling conflicting definitions (e.g., type mismatches).
        raise NotImplementedError("'union' merge strategy is not yet implemented.")

    elif merge_strategy == 'intersection':
        # TODO: Implement schema intersection logic (more complex)
        # - Include only fields present in *all* profiles.
        # - Need rules for ensuring compatibility of definitions for common fields.
        raise NotImplementedError("'intersection' merge strategy is not yet implemented.")

    else:
        raise ValueError(f"Unsupported merge strategy: '{merge_strategy}'")

    save_profile(merged_profile)
    return merged_profile

def find_profiles_by_schema_element(
    element_path: str,
    value_matcher: Optional[Any] = None
) -> List[AnalysisProfile]:
    """
    Finds profiles where a specific schema element exists or matches a value.

    Args:
        element_path: Dot notation path to the schema element (e.g., 'inputs.user_query.type').
        value_matcher: Optional. If provided, the element's value must match this.
                       If None, just checks for the element's existence.

    Returns:
        List of matching profiles.
    """
    all_profiles = list_all_profiles()
    matching_profiles = []
    path_parts = element_path.split('.')

    for profile in all_profiles:
        current_value = profile.schema_definition
        found = True
        try:
            for part in path_parts:
                if isinstance(current_value, dict):
                    if part in current_value:
                        current_value = current_value[part]
                    else:
                        found = False
                        break
                # TODO: Handle list indices? e.g., 'outputs.items[0].name'
                else:
                    found = False # Path doesn't continue
                    break
            
            if found:
                if value_matcher is not None:
                    # Check if the found element's value matches
                    if current_value == value_matcher:
                        matching_profiles.append(profile)
                else:
                    # Only checking for existence, and we found it
                    matching_profiles.append(profile)
        except Exception:
             # Ignore errors during traversal (e.g., unexpected structure)
            continue
            
    return matching_profiles

def extract_schema_section(profile_id_or_name: str, section_path: str) -> Optional[Any]:
    """
    Extracts a specific part (section or element) from a profile's schema.

    Args:
        profile_id_or_name: ID or Name of the profile.
        section_path: Dot notation path to the schema section (e.g., 'inputs', 'outputs.summary').

    Returns:
        The extracted section (could be dict, list, string, etc.), or None if not found.
        Returns a deep copy to prevent modification of the original profile schema.
    
    Raises:
        ValueError: If the profile is not found.
    """
    profile = load_profile(profile_id_or_name)
    if not profile:
        raise ValueError(f"Profile '{profile_id_or_name}' not found.")

    current_section = profile.schema_definition
    path_parts = section_path.split('.')
    
    try:
        for part in path_parts:
            if isinstance(current_section, dict):
                if part in current_section:
                    current_section = current_section[part]
                else:
                    return None # Path part not found
            # TODO: Handle list indices?
            else:
                return None # Cannot traverse further
        
        # Return a deep copy to prevent modification of the original
        return copy.deepcopy(current_section)
    except Exception:
        return None # Error during traversal

# --- Add other utility functions from task details as needed --- 