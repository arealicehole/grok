import uuid
import copy
import deepdiff
from datetime import datetime
from typing import List, Dict, Optional, Tuple, Any, TYPE_CHECKING, Callable
import json
import os
import customtkinter as ctk # For file dialogs
from CTkMessagebox import CTkMessagebox # For confirmation/info messages
import logging # For logging in utilities

# Placeholder for actual model and storage implementation
# Assume these exist and provide the necessary interface
from .models.analysis_profile import AnalysisProfile # Corrected import path
# Assume storage functions exist (e.g., in src/profile_storage.py)

# Use TYPE_CHECKING to avoid circular import for type hinting
if TYPE_CHECKING:
    from .storage_manager import StorageManager

# Setup logger for utilities
logger = logging.getLogger(__name__)

def clone_profile(storage_manager: 'StorageManager', profile_id_str: str, new_name: str = None, modifications: dict = None) -> AnalysisProfile:
    """
    Creates a copy of an existing profile with optional modifications.

    Args:
        storage_manager: The StorageManager instance to use for data access.
        profile_id_str: ID of the profile to clone.
        new_name: Optional new name (defaults to "Copy of [original name]").
        modifications: Dictionary of attributes to modify in the new profile.

    Returns:
        The newly created and saved profile.

    Raises:
        ValueError: If the source profile is not found or if the new_name conflicts.
    """
    logger.info(f"Attempting to clone profile ID: {profile_id_str} into new profile '{new_name}'")
    try:
        # Load the original profile using the provided ID
        original_profile = storage_manager.load_profile(profile_id_str)

        if not original_profile:
            logger.error(f"Clone failed: Original profile with ID {profile_id_str} not found.")
            raise ValueError(f"Source profile '{profile_id_str}' not found.")

        target_name = new_name or f"Copy of {original_profile.name}"

        # Check for name conflict before proceeding
        if storage_manager.profile_exists(target_name):
            raise ValueError(f"A profile with the name '{target_name}' already exists.")

        # Deep copy to avoid reference issues with nested objects like schema_definition
        new_profile = copy.deepcopy(original_profile)
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
        storage_manager.save_profile(new_profile)
        return new_profile
    except Exception as e:
        logger.error(f"Error cloning profile: {e}", exc_info=True)
        raise ValueError(f"Error cloning profile: {e}") from e

def create_template_profile(storage_manager: 'StorageManager', template_type: str, name: str = None) -> AnalysisProfile:
    """
    Creates a pre-configured profile based on common use cases.

    Args:
        storage_manager: The StorageManager instance to use for data access.
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
    if storage_manager.profile_exists(profile_name):
        raise ValueError(f"A profile with the name '{profile_name}' already exists.")

    profile = AnalysisProfile(
        name=profile_name,
        schema_definition=template_config["schema_definition"],
        instructions=template_config["instructions"]
    )

    storage_manager.save_profile(profile)
    return profile

def diff_profiles(storage_manager: 'StorageManager', profile1_id_or_name: str, profile2_id_or_name: str) -> dict:
    """
    Compares two profiles and returns their differences using deepdiff.

    Args:
        storage_manager: The StorageManager instance to use for data access.
        profile1_id_or_name: ID or Name of the first profile.
        profile2_id_or_name: ID or Name of the second profile.

    Returns:
        A dictionary representing the differences, as returned by deepdiff.
        Excludes metadata fields (id, created_at, updated_at) from comparison.

    Raises:
        ValueError: If either profile is not found.
    """
    profile1 = storage_manager.load_profile(profile1_id_or_name)
    profile2 = storage_manager.load_profile(profile2_id_or_name)

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

def search_profiles_by_text(storage_manager: 'StorageManager', query: str, search_fields: Optional[List[str]] = None) -> List[AnalysisProfile]:
    """
    Performs a simple case-insensitive text search across profile fields.

    Args:
        storage_manager: The StorageManager instance to use for data access.
        query: Text to search for.
        search_fields: List of fields to search (defaults to ['name', 'instructions']).
                       Can include nested fields in schema_definition using dot notation
                       (e.g., 'schema_definition.inputs.transcript.description').

    Returns:
        List of matching profiles.
    """
    if search_fields is None:
        search_fields = ['name', 'instructions']

    all_profiles = storage_manager.get_all_profiles()
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
    storage_manager: 'StorageManager',
    profile_ids_or_names: List[str],
    new_name: str,
    merge_strategy: str = 'primary'
) -> AnalysisProfile:
    """
    Combines elements from multiple profiles into a new profile.

    Args:
        storage_manager: The StorageManager instance to use for data access.
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
    if storage_manager.profile_exists(new_name):
        raise ValueError(f"A profile with the name '{new_name}' already exists.")

    profiles = []
    for pid_or_name in profile_ids_or_names:
        profile = storage_manager.load_profile(pid_or_name)
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

    storage_manager.save_profile(merged_profile)
    return merged_profile

def find_profiles_by_schema_element(
    storage_manager: 'StorageManager',
    element_path: str,
    value_matcher: Optional[Any] = None
) -> List[AnalysisProfile]:
    """
    Finds profiles where a specific schema element exists or matches a value.

    Args:
        storage_manager: The StorageManager instance to use for data access.
        element_path: Dot notation path to the schema element (e.g., 'inputs.user_query.type').
        value_matcher: Optional. If provided, the element's value must match this.
                       If None, just checks for the element's existence.

    Returns:
        List of matching profiles.
    """
    all_profiles = storage_manager.get_all_profiles()
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

def extract_schema_section(storage_manager: 'StorageManager', profile_id_or_name: str, section_path: str) -> Optional[Any]:
    """
    Extracts a specific part (section or element) from a profile's schema.

    Args:
        storage_manager: The StorageManager instance to use for data access.
        profile_id_or_name: ID or Name of the profile.
        section_path: Dot notation path to the schema section (e.g., 'inputs', 'outputs.summary').

    Returns:
        The extracted section (could be dict, list, string, etc.), or None if not found.
        Returns a deep copy to prevent modification of the original profile schema.
    
    Raises:
        ValueError: If the profile is not found.
    """
    profile = storage_manager.load_profile(profile_id_or_name)
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

# --- Functions added for Subtask 3.4 ---

def delete_profile(storage_manager: 'StorageManager', profile_id_or_name: str) -> bool:
    """
    Deletes a profile by its ID or Name using the StorageManager.

    Args:
        storage_manager: The StorageManager instance.
        profile_id_or_name: ID or Name of the profile to delete.

    Returns:
        True if the profile was found and deleted, False otherwise.

    Raises:
        ProfileStorageError: For underlying storage issues.
    """
    try:
        # Attempt to load first to ensure it exists (StorageManager might handle this)
        profile_to_delete = storage_manager.load_profile(profile_id_or_name)
        if not profile_to_delete:
             logger.warning(f"Profile '{profile_id_or_name}' not found for deletion via StorageManager.")
             return False
        
        # Use the storage manager's delete method (which likely takes ID)
        deleted = storage_manager.delete_profile(str(profile_to_delete.id))
        if deleted:
            logger.info(f"Successfully deleted profile '{profile_to_delete.name}' (ID: {profile_to_delete.id}) via StorageManager.")
        else:
             # This might indicate an issue if load succeeded but delete failed
             logger.warning(f"StorageManager reported failure deleting profile ID {profile_to_delete.id} after finding it.")
        return deleted
    except ProfileNotFoundError:
         logger.warning(f"Profile '{profile_id_or_name}' not found during deletion attempt.")
         return False
    except Exception as e:
        logger.error(f"Error deleting profile '{profile_id_or_name}' via StorageManager: {e}", exc_info=True)
        # Optionally re-raise a more specific error or return False
        # raise ProfileStorageError(f"Failed to delete profile: {e}") from e
        return False

def export_profile(storage_manager: 'StorageManager', profile_id_or_name: str, file_path: str) -> bool:
    """
    Exports a profile to a JSON file using the StorageManager.

    Args:
        storage_manager: The StorageManager instance.
        profile_id_or_name: ID or Name of the profile to export.
        file_path: The full path to save the JSON file.

    Returns:
        True if export was successful, False otherwise.

    Raises:
        ValueError: If the profile is not found by the storage manager.
        IOError: If there's an error writing the file.
        NotImplementedError: If the storage backend doesn't support export.
    """
    try:
        # Use StorageManager's export method which returns the JSON string
        profile_json = storage_manager.export_profile_to_json(profile_id_or_name)
        
        # Ensure parent directory exists
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(profile_json) # Write the JSON string directly
        logger.info(f"Exported profile '{profile_id_or_name}' to {file_path} via StorageManager.")
        return True
    except (ProfileNotFoundError, ValueError) as e: # Catch not found/validation from StorageManager
        logger.error(f"Could not find or validate profile '{profile_id_or_name}' for export: {e}")
        raise ValueError(f"Profile '{profile_id_or_name}' not found or invalid for export.") from e
    except NotImplementedError as e:
         logger.error(f"Export not supported by current storage backend: {e}")
         raise # Re-raise NotImplementedError
    except IOError as e:
        logger.error(f"Failed to write profile to {file_path}: {e}")
        raise # Re-raise IO errors
    except Exception as e:
        logger.exception(f"Unexpected error during profile export via StorageManager: {e}")
        return False

def import_profile(storage_manager: 'StorageManager', file_path: str, handle_name_conflicts: str = 'rename') -> Optional[AnalysisProfile]:
    """
    Imports a profile from a JSON file using the StorageManager.

    Args:
        storage_manager: The StorageManager instance.
        file_path: Path to the JSON file to import.
        handle_name_conflicts: How to handle name conflicts ('rename', 'error', 'overwrite').

    Returns:
        The imported and saved AnalysisProfile object, or None if import failed.

    Raises:
        FileNotFoundError: If the file_path does not exist.
        ValueError: If JSON is invalid, missing required fields, or name conflict occurs with 'error' strategy.
        NotImplementedError: If the storage backend doesn't support import.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Import file not found: {file_path}")

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            profile_json_string = f.read()
            
        # Use StorageManager's import method
        imported_profile = storage_manager.import_profile_from_json(
            profile_json_string=profile_json_string,
            handle_name_conflicts=handle_name_conflicts
        )
        
        if imported_profile:
             logger.info(f"Successfully imported profile '{imported_profile.name}' from {file_path} via StorageManager.")
             return imported_profile
        else:
             # Should not happen if import_profile_from_json raises on error
             logger.warning(f"Import from {file_path} via StorageManager returned None unexpectedly.")
             return None
             
    except (json.JSONDecodeError, ValueError) as e:
        logger.error(f"Failed to decode or validate JSON from {file_path}: {e}")
        raise ValueError(f"Invalid profile data in {file_path}: {e}") from e
    except FileNotFoundError: # Should be caught above, but double-check
         raise
    except NotImplementedError as e:
         logger.error(f"Import not supported by current storage backend: {e}")
         raise # Re-raise NotImplementedError
    except Exception as e:
        logger.exception(f"Unexpected error during profile import via StorageManager from {file_path}: {e}")
        return None

# --- End functions added for Subtask 3.4 ---

# --- New Utility Functions for Export/Import with UI Interaction ---

def export_profile_utility(storage_manager: 'StorageManager', profile_id_str: str):
    """
    Handles the export process, including the file dialog.
    Uses CTkMessagebox for feedback.
    """
    # Get profile name for default filename
    profile_name_safe = "profile_export"
    try:
        profile = storage_manager.load_profile(profile_id_str)
        if profile:
            # Make filename safe
            profile_name_safe = "".join(c if c.isalnum() or c in (' ', '_', '-') else '_' for c in profile.name).rstrip()
        else:
             CTkMessagebox(title="Error", message=f"Profile '{profile_id_str}' not found for export.", icon="cancel")
             return
    except Exception as e:
        logger.warning(f"Could not load profile {profile_id_str} to get name for export filename: {e}")

    file_path = ctk.filedialog.asksaveasfilename(
        title="Export Profile As",
        defaultextension=".json",
        initialfile=f"{profile_name_safe}.json",
        filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
    )

    if file_path: # Check if user selected a file and didn't cancel
        try:
            # Access the underlying repository method via storage_manager
            # Assumes _storage attribute exists and has the export method
            # TODO: Add a wrapper in StorageManager for cleaner access
            if not hasattr(storage_manager._storage, 'export_profile_to_json'):
                 raise NotImplementedError("Export functionality not implemented in the current storage backend.")

            profile_json = storage_manager._storage.export_profile_to_json(profile_id_str)

            # Ensure parent directory exists
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            with open(file_path, 'w', encoding='utf-8') as f:
                 f.write(profile_json)
            logger.info(f"Profile '{profile.name if profile else profile_id_str}' exported to {file_path}")
            CTkMessagebox(title="Success", message=f"Profile exported successfully to:\n{file_path}", icon="check")

        except (ValueError, IOError, NotImplementedError) as e: # Catch specific expected errors
             logger.error(f"Failed to export profile: {e}", exc_info=True)
             CTkMessagebox(title="Export Error", message=f"Failed to export profile: {e}", icon="cancel")
        except Exception as e:
             logger.exception(f"Unexpected error during profile export utility: {e}")
             CTkMessagebox(title="Error", message=f"An unexpected error occurred during export: {e}", icon="cancel")

def import_profile_utility(storage_manager: 'StorageManager', on_success_callback: Optional[Callable] = None):
    """
    Handles the import process, including file dialog and conflict resolution.
    Uses CTkMessagebox for feedback.
    Calls the optional callback on successful import.
    """
    file_path = ctk.filedialog.askopenfilename(
        title="Import Profile From",
        filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
    )

    if file_path: # Check if user selected a file and didn't cancel
        try:
            # Ask user how to handle name conflicts
            conflict_dialog = CTkMessagebox(title="Import Conflict Handling", 
                                            message="If an imported profile name already exists, how should it be handled?",
                                            icon="question", options=["Rename Automatically", "Overwrite Existing", "Cancel Import"])
            conflict_choice = conflict_dialog.get()

            strategy = None
            if conflict_choice == "Rename Automatically":
                strategy = 'rename'
            elif conflict_choice == "Overwrite Existing":
                 strategy = 'overwrite'
            elif conflict_choice == "Cancel Import" or conflict_choice is None:
                 logger.info("Profile import cancelled by user choice.")
                 return
            else: # Should not happen with CTkMessagebox options
                 logger.warning(f"Unknown conflict choice: {conflict_choice}. Cancelling import.")
                 return

            # Read the file content
            with open(file_path, 'r', encoding='utf-8') as f:
                 profile_json_string = f.read()

            # Access the underlying repository method via storage_manager
            # Assumes _storage attribute exists and has the import method
            # TODO: Add a wrapper in StorageManager for cleaner access
            if not hasattr(storage_manager._storage, 'import_profile_from_json'):
                 raise NotImplementedError("Import functionality not implemented in the current storage backend.")

            imported_profile = storage_manager._storage.import_profile_from_json(
                profile_json_string=profile_json_string,
                handle_name_conflicts=strategy
            )
            
            if imported_profile:
                logger.info(f"Profile '{imported_profile.name}' imported successfully from {file_path}")
                CTkMessagebox(title="Success", message=f"Profile '{imported_profile.name}' imported successfully!", icon="check")
                if on_success_callback:
                    on_success_callback() # e.g., refresh profile list in UI
            else:
                 # import_profile_from_json should raise exceptions on failure
                 # This case might occur if it returns None unexpectedly
                 logger.warning(f"Import from {file_path} completed but returned no profile object.")
                 CTkMessagebox(title="Import Issue", message="Profile import finished, but no profile data was returned. Check logs.", icon="warning")

        except (FileNotFoundError, ValueError, json.JSONDecodeError, NotImplementedError) as e: # Catch specific expected errors
             logger.error(f"Failed to import profile: {e}", exc_info=True)
             CTkMessagebox(title="Import Error", message=f"Failed to import profile: {e}", icon="cancel")
        except Exception as e:
             logger.exception(f"Unexpected error during profile import utility: {e}")
             CTkMessagebox(title="Error", message=f"An unexpected error occurred during import: {e}", icon="cancel")
        

# --- End new Utility Functions --- 