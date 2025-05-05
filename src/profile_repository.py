import sqlite3
import json
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List, Tuple
import uuid
import logging
import os
import time # Added for retry logic
import functools # Added for decorator
# --- Import consolidated exceptions ---
from .exceptions import (
    ProfileStorageError,
    ProfileNotFoundError,
    ProfileValidationError,
    ProfileStorageConnectionError,
    ProfileConcurrencyError,
    ProfileCorruptionError,
    ProfileDatabaseError,
    BatchProcessingError,
    map_sqlite_exception
)
# ---------------------------------

# --- Add validation imports ---
from .validation import (
    ValidationResult,
    validate_profile_name,
    validate_profile_instructions,
    validate_schema_definition_basic,
    validate_schema_against_standard,
    sanitize_string
)
# -----------------------------

# Assuming AnalysisProfile is defined here or importable
# from .analysis_profile import AnalysisProfile 
# Placeholder until AnalysisProfile is properly located/defined
class AnalysisProfile:
    def __init__(self, id=None, name=None, instructions=None, schema_definition=None, created_at=None, updated_at=None):
        self.id = id or str(uuid.uuid4())
        self.name = name
        self.instructions = instructions
        self.schema_definition = schema_definition or {}
        self.created_at = created_at or datetime.now(timezone.utc)
        self.updated_at = updated_at or self.created_at

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'name': self.name,
            'instructions': self.instructions,
            'schema_definition': self.schema_definition,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AnalysisProfile':
        return cls(
            id=data.get('id'),
            name=data.get('name'),
            instructions=data.get('instructions'),
            schema_definition=data.get('schema_definition'),
            created_at=datetime.fromisoformat(data['created_at']) if data.get('created_at') else None,
            updated_at=datetime.fromisoformat(data['updated_at']) if data.get('updated_at') else None,
        )

# --- Helper Decorator for Error Handling ---
def handle_db_errors(operation_name: str):
    """Decorator to wrap database operations with common error handling, logging, and retries for lock errors."""
    MAX_RETRIES = 3
    INITIAL_BACKOFF_SECONDS = 0.2

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            repo_instance = args[0]
            last_exception = None
            for attempt in range(MAX_RETRIES):
                try:
                    return func(*args, **kwargs)
                except sqlite3.OperationalError as e:
                    # Check specifically for database locked error
                    if "database is locked" in str(e).lower():
                        last_exception = e
                        if attempt < MAX_RETRIES - 1:
                            backoff = INITIAL_BACKOFF_SECONDS * (2 ** attempt)
                            repo_instance.logger.warning(
                                f"Database locked during '{operation_name}' (attempt {attempt + 1}/{MAX_RETRIES}). Retrying in {backoff:.2f}s..."
                            )
                            time.sleep(backoff)
                            continue # Retry the operation
                        else:
                            # Max retries reached for lock error
                            repo_instance.logger.error(
                                f"Database lock persisted after {MAX_RETRIES} attempts during '{operation_name}': {e}", exc_info=False
                            )
                            # Map the *original* lock exception
                            raise map_sqlite_exception(e) 
                    else:
                        # OperationalError, but not a lock error
                        repo_instance.logger.error(f"SQLite OperationalError during '{operation_name}': {e}", exc_info=True)
                        raise map_sqlite_exception(e)
                except sqlite3.Error as e: # Catch other sqlite3 errors
                    last_exception = e
                    repo_instance.logger.error(f"SQLite error during '{operation_name}': {e}", exc_info=True)
                    raise map_sqlite_exception(e) # Map and raise immediately
                except Exception as e: # Catch other non-sqlite potential errors
                    last_exception = e
                    repo_instance.logger.error(f"Unexpected error during '{operation_name}': {e}", exc_info=True)
                    raise # Re-raise non-sqlite errors directly
            
            # This part should ideally not be reached if exceptions are always raised on failure,
            # but added as a safeguard. It implies all retries failed without raising properly.
            repo_instance.logger.critical(f"Operation '{operation_name}' failed after {MAX_RETRIES} attempts without explicit exception raise.")
            if last_exception:
                 # Try mapping the last known sqlite error if possible
                 if isinstance(last_exception, sqlite3.Error):
                      raise map_sqlite_exception(last_exception)
                 else:
                      raise ProfileStorageError(f"Operation '{operation_name}' failed after retries.") from last_exception
            else:
                 raise ProfileStorageError(f"Operation '{operation_name}' failed unexpectedly after retries.")

        return wrapper
    return decorator
# -----------------------------------------

# --- Profile Repository ---
class ProfileRepository:
    """Handles persistence of AnalysisProfile objects using SQLite."""

    def __init__(self, db_path: Optional[str] = None):
        """
        Initializes the repository.

        Args:
            db_path: Path to the SQLite database file. Defaults to 
                     ~/.config/grok_analyzer/profiles.db
        """
        if db_path is None:
            # Default path: ~/.config/grok_analyzer/profiles.db
            config_dir = os.path.join(os.path.expanduser("~"), ".config", "grok_analyzer")
            os.makedirs(config_dir, exist_ok=True)
            self.db_path = os.path.join(config_dir, "profiles.db")
        else:
            self.db_path = db_path
            
        self.logger = logging.getLogger(__name__)
        self._ensure_table_exists()

    @handle_db_errors("get_connection")
    def _get_connection(self) -> sqlite3.Connection:
        """Establishes and returns a new database connection."""
        # Using WAL mode for better concurrency
        conn = sqlite3.connect(self.db_path, timeout=10.0) 
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.row_factory = sqlite3.Row # Return rows as dict-like objects
        return conn

    @handle_db_errors("ensure_table_exists")
    def _ensure_table_exists(self):
        """Ensures the 'profiles' table exists in the database."""
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS profiles (
            id TEXT PRIMARY KEY,
            name TEXT UNIQUE NOT NULL,
            instructions TEXT,
            schema_definition TEXT NOT NULL, -- Stored as JSON string
            created_at TEXT NOT NULL,      -- ISO format string
            updated_at TEXT NOT NULL       -- ISO format string
        );
        """
        create_name_index_sql = "CREATE INDEX IF NOT EXISTS idx_profiles_name ON profiles(name);"
        create_updated_at_index_sql = "CREATE INDEX IF NOT EXISTS idx_profiles_updated_at ON profiles(updated_at);"
        
        with self._get_connection() as conn:
            conn.execute(create_table_sql)
            conn.execute(create_name_index_sql)
            conn.execute(create_updated_at_index_sql)
            conn.commit()
        self.logger.info(f"Ensured 'profiles' table exists in {self.db_path}")

    def _serialize_profile(self, profile: AnalysisProfile) -> Tuple[str, str, Optional[str], str, str, str]:
        """Converts an AnalysisProfile object into a tuple for database insertion/update."""
        if not isinstance(profile, AnalysisProfile):
             raise TypeError("Input must be an AnalysisProfile object")
        
        return (
            str(profile.id),
            profile.name,
            profile.instructions,
            json.dumps(profile.schema_definition or {}), # Ensure valid JSON
            profile.created_at.isoformat(),
            profile.updated_at.isoformat()
        )

    def _deserialize_profile(self, row: sqlite3.Row) -> AnalysisProfile:
        """Converts a database row (sqlite3.Row) into an AnalysisProfile object."""
        if not isinstance(row, sqlite3.Row):
             raise TypeError("Input must be a sqlite3.Row object")
             
        profile_id = row["id"] # Get ID for logging context
        try:
            schema_def = json.loads(row["schema_definition"]) if row["schema_definition"] else {}
        except json.JSONDecodeError as e:
            # Log the error and raise a specific exception indicating data corruption
            self.logger.error(f"JSON decode error for schema_definition in profile ID {profile_id}: {e}")
            raise ProfileCorruptionError(f"Failed to decode schema for profile {profile_id}. Data may be corrupt.") from e
        except Exception as e: # Catch unexpected errors during deserialization
            self.logger.error(f"Unexpected error deserializing profile ID {profile_id}: {e}", exc_info=True)
            raise ProfileStorageError(f"Failed to deserialize profile {profile_id}") from e

        # Convert timestamps safely
        try:
             created_at = datetime.fromisoformat(row["created_at"]) if row.get("created_at") else None
             updated_at = datetime.fromisoformat(row["updated_at"]) if row.get("updated_at") else None
             if created_at is None or updated_at is None:
                 raise ValueError("Missing timestamp data")
        except (TypeError, ValueError) as e:
             self.logger.error(f"Timestamp conversion error for profile ID {profile_id}: {e}")
             raise ProfileCorruptionError(f"Invalid timestamp format for profile {profile_id}. Data may be corrupt.") from e

        return AnalysisProfile(
            id=profile_id,
            name=row["name"],
            instructions=row["instructions"],
            schema_definition=schema_def,
            created_at=created_at,
            updated_at=updated_at
        )

    # --- Validation Orchestrator ---
    def _validate_profile_data(self, profile: AnalysisProfile, is_update: bool = False) -> ValidationResult:
        """Runs all validations for an Analysis Profile instance."""
        full_result = ValidationResult()

        # Check name uniqueness
        try:
             existing_profile_with_name = self.get_profile_by_name(profile.name)
        except ProfileNotFoundError:
             existing_profile_with_name = None
        # Let other ProfileStorageErrors propagate

        is_duplicate_name = False
        if existing_profile_with_name:
            if is_update:
                # If updating, it's a duplicate only if the found ID is different
                if str(existing_profile_with_name.id) != str(profile.id):
                    is_duplicate_name = True
            else:
                # If creating, any existing profile with the same name is a duplicate
                is_duplicate_name = True
        
        if is_duplicate_name:
             full_result.add_error("name", f"Profile name '{profile.name}' already exists.")

        # Field validations 
        full_result.merge(validate_profile_name(profile.name, existing_names=None)) # Uniqueness checked above
        full_result.merge(validate_profile_instructions(profile.instructions))
        
        # Basic Schema Checks (Type, Serializability)
        basic_schema_result = validate_schema_definition_basic(profile.schema_definition)
        full_result.merge(basic_schema_result)

        # Detailed JSON Schema Standard Validation (only if basic check passed and schema exists)
        if basic_schema_result.is_valid and isinstance(profile.schema_definition, dict) and profile.schema_definition:
             # Replace old structure check with standard validation
             # full_result.merge(validate_schema_structure(profile.schema_definition)) # Deprecated
             full_result.merge(validate_schema_against_standard(profile.schema_definition)) 

        # TODO: Add business rule validations (e.g., prevent deletion of used profiles - needs context)

        return full_result

    # --- CRUD Methods will be added below ---

    @handle_db_errors("create_profile")
    def create_profile(self, profile: AnalysisProfile) -> AnalysisProfile:
        """Inserts a new profile into the database after validation."""
        insert_sql = "INSERT INTO profiles (id, name, instructions, schema_definition, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)"
        
        # Ensure created_at and updated_at are set
        now = datetime.now(timezone.utc)
        profile.created_at = profile.created_at or now
        profile.updated_at = profile.updated_at or profile.created_at
        profile.id = profile.id or str(uuid.uuid4()) # Ensure ID exists

        # --- Perform Validation ---
        validation_result = self._validate_profile_data(profile, is_update=False)
        if not validation_result:
            self.logger.warning(f"Validation failed for creating profile '{profile.name}': {validation_result}")
            raise ProfileValidationError(f"Validation failed for profile '{profile.name}'", validation_result=validation_result)
        # ------------------------

        # --- Apply Sanitization ---
        profile.name = sanitize_string(profile.name)
        profile.instructions = sanitize_string(profile.instructions)
        # Note: Schema sanitization might need a deeper approach depending on content
        # -------------------------

        try:
            profile_tuple = self._serialize_profile(profile)
        except TypeError as e:
             self.logger.error(f"Serialization error for profile {profile.id}: {e}")
             raise ValueError(f"Invalid profile data provided: {e}") from e
             
        try:
            with self._get_connection() as conn:
                conn.execute(insert_sql, profile_tuple)
                conn.commit()
            self.logger.info(f"Successfully created profile ID: {profile.id}, Name: {profile.name}")
            return profile
        except sqlite3.IntegrityError as e:
            self.logger.warning(f"Failed to create profile due to IntegrityError: {e}")
            # Check if it's a name or ID conflict
            if "UNIQUE constraint failed: profiles.name" in str(e):
                raise ProfileDuplicateError(f"Profile with name '{profile.name}' already exists.") from e
            elif "UNIQUE constraint failed: profiles.id" in str(e):
                raise ProfileDuplicateError(f"Profile with ID '{profile.id}' already exists (collision). Regenerate ID.") from e
            else:
                # Other integrity errors (e.g., NOT NULL constraint if schema changes)
                 raise ProfileStorageError(f"Database integrity error: {e}") from e
        except sqlite3.Error as e:
            self.logger.error(f"Database error while creating profile {profile.id}: {e}")
            raise ProfileStorageError(f"Failed to create profile in database: {e}") from e

    @handle_db_errors("get_profile_by_id")
    def get_profile_by_id(self, profile_id: str) -> Optional[AnalysisProfile]:
        """Retrieves a profile by its unique ID."""
        select_sql = "SELECT * FROM profiles WHERE id = ?"
        
        if not profile_id:
             raise ValueError("Profile ID cannot be empty")
             
        try:
            # Validate if the profile_id looks like a UUID, though the DB stores it as TEXT
            # uuid.UUID(profile_id) # Uncomment if strict UUID format is required for input
            pass
        except ValueError:
             raise ValueError("Invalid Profile ID format. Expected UUID string.")

        try:
            with self._get_connection() as conn:
                cursor = conn.execute(select_sql, (profile_id,))
                row = cursor.fetchone()
            
            if row:
                self.logger.debug(f"Retrieved profile by ID: {profile_id}")
                return self._deserialize_profile(row)
            else:
                self.logger.debug(f"No profile found with ID: {profile_id}")
                return None
        except sqlite3.Error as e:
            self.logger.error(f"Database error while retrieving profile by ID '{profile_id}': {e}")
            raise ProfileStorageError(f"Failed to retrieve profile by ID: {e}") from e

    @handle_db_errors("get_profile_by_name")
    def get_profile_by_name(self, profile_name: str) -> Optional[AnalysisProfile]:
        """Retrieves a profile by its unique name."""
        select_sql = "SELECT * FROM profiles WHERE name = ?"
        
        if not profile_name:
            raise ValueError("Profile name cannot be empty")

        try:
            with self._get_connection() as conn:
                cursor = conn.execute(select_sql, (profile_name,))
                row = cursor.fetchone()
            
            if row:
                self.logger.debug(f"Retrieved profile by name: {profile_name}")
                return self._deserialize_profile(row)
            else:
                self.logger.debug(f"No profile found with name: {profile_name}")
                return None # Explicitly return None if not found
        except sqlite3.Error as e:
            self.logger.error(f"Database error while retrieving profile by name '{profile_name}': {e}")
            raise ProfileStorageError(f"Failed to retrieve profile by name: {e}") from e

    @handle_db_errors("get_all_profiles")
    def get_all_profiles(self, filters: Optional[Dict] = None, page: int = 1, page_size: int = 20, sort_by: str = 'name', sort_order: str = 'ASC') -> List[AnalysisProfile]:
        """
        Retrieves a list of profiles, supporting filtering and pagination.

        Args:
            filters: Optional dictionary for filtering profiles.
                     Supported filters: 'name' (partial match), 'created_after' (ISO date string)
            page: Page number for pagination (1-indexed).
            page_size: Number of profiles per page.
            sort_by: Field to sort by (e.g., 'name', 'created_at', 'updated_at'). Default 'name'.
            sort_order: Sort order ('ASC' or 'DESC'). Default 'ASC'.

        Returns:
            A list of AnalysisProfile objects.
        """
        query = "SELECT * FROM profiles"
        params: List[Any] = []
        where_clauses = []

        if filters:
            if 'name' in filters and filters['name']:
                where_clauses.append("name LIKE ?")
                params.append(f"%{filters['name']}%") # Partial match
            if 'created_after' in filters and filters['created_after']:
                try:
                    # Validate date format
                    datetime.fromisoformat(str(filters['created_after']).replace('Z', '+00:00')) 
                    where_clauses.append("created_at > ?")
                    params.append(str(filters['created_after']))
                except ValueError:
                    self.logger.warning(f"Invalid date format for created_after filter: {filters['created_after']}")
                    raise ValueError("Invalid date format for created_after filter. Use ISO format.")
            # Add more filters here as needed

        if where_clauses:
            query += " WHERE " + " AND ".join(where_clauses)

        # Sorting
        allowed_sort_fields = ['name', 'created_at', 'updated_at']
        if sort_by not in allowed_sort_fields:
            self.logger.warning(f"Invalid sort_by field: {sort_by}. Defaulting to 'name'.")
            sort_by = 'name'
            
        order = 'ASC' if sort_order.upper() == 'ASC' else 'DESC' # Default to ASC if invalid
        query += f" ORDER BY {sort_by} {order}" 

        # Pagination
        if page < 1:
             page = 1
        if page_size < 1:
             page_size = 20 # Default page size
             
        offset = (page - 1) * page_size
        query += f" LIMIT ? OFFSET ?"
        params.extend([page_size, offset])

        profiles = []
        try:
            with self._get_connection() as conn:
                self.logger.debug(f"Executing query: {query} with params: {params}")
                cursor = conn.execute(query, params)
                rows = cursor.fetchall()
            
            for row in rows:
                try:
                     profiles.append(self._deserialize_profile(row))
                except (TypeError, json.JSONDecodeError, ValueError) as deser_error:
                     # Log error for the specific row but continue processing others
                     self.logger.error(f"Failed to deserialize profile row ID {row.get('id', 'N/A')}: {deser_error}")
                     # Optionally, you could add a placeholder or skip the problematic row

            self.logger.info(f"Retrieved {len(profiles)} profiles (Page {page}, Size {page_size}) with filters: {filters}")
            return profiles
        except sqlite3.Error as e:
            self.logger.error(f"Database error while retrieving profiles: {e}")
            raise ProfileStorageError(f"Failed to retrieve profiles: {e}") from e

    @handle_db_errors("update_profile")
    def update_profile(self, profile: AnalysisProfile) -> AnalysisProfile:
        """Updates an existing profile in the database after validation."""
        update_sql = """
        UPDATE profiles 
        SET name = ?, instructions = ?, schema_definition = ?, updated_at = ?
        WHERE id = ?
        """

        # Ensure updated_at is set
        profile.updated_at = datetime.now(timezone.utc)

        # --- Perform Validation ---
        # Ensure the profile we are trying to update actually exists first
        existing_profile = self.get_profile_by_id(profile.id)
        if not existing_profile:
             raise ProfileNotFoundError(f"Profile with ID '{profile.id}' not found, cannot update.")

        validation_result = self._validate_profile_data(profile, is_update=True)
        if not validation_result:
            self.logger.warning(f"Validation failed for updating profile '{profile.name}' (ID: {profile.id}): {validation_result}")
            raise ProfileValidationError(f"Validation failed for profile '{profile.name}'", validation_result=validation_result)
        # ------------------------

        # --- Apply Sanitization ---
        profile.name = sanitize_string(profile.name)
        profile.instructions = sanitize_string(profile.instructions)
        # Note: Schema sanitization might need a deeper approach depending on content
        # -------------------------
        
        try:
             # We only update specific fields, don't re-serialize the whole object initially
             schema_json = json.dumps(profile.schema_definition or {})
             update_tuple = (
                 profile.name,
                 profile.instructions,
                 schema_json,
                 profile.updated_at.isoformat(),
                 profile.id
             )
        except (TypeError, json.JSONDecodeError) as e:
             self.logger.error(f"Serialization/Schema error during update prep for profile {profile.id}: {e}")
             raise ValueError(f"Invalid profile data for update: {e}") from e

        try:
            with self._get_connection() as conn:
                cursor = conn.execute(update_sql, update_tuple)
                if cursor.rowcount == 0:
                    # This should ideally not happen if get_profile_by_id check passed, but good to have
                    raise ProfileNotFoundError(f"Profile with ID '{profile.id}' not found during update operation.")
                conn.commit()
            self.logger.info(f"Successfully updated profile ID: {profile.id}, Name: {profile.name}")
            # Return the updated profile object passed in (already modified)
            return profile 
        except sqlite3.IntegrityError as e:
             # This primarily catches name conflicts if another profile took the name
             # between the validation check and the update commit.
             self.logger.warning(f"Failed to update profile {profile.id} due to IntegrityError: {e}")
             if "UNIQUE constraint failed: profiles.name" in str(e):
                 raise ProfileDuplicateError(f"Profile name '{profile.name}' is already taken by another profile.") from e
             else:
                 raise ProfileStorageError(f"Database integrity error during update: {e}") from e
        except sqlite3.Error as e:
            self.logger.error(f"Database error while updating profile {profile.id}: {e}")
            raise ProfileStorageError(f"Failed to update profile in database: {e}") from e

    @handle_db_errors("delete_profile")
    def delete_profile(self, profile_id: str) -> bool:
        """Deletes a profile by its ID."""
        delete_sql = "DELETE FROM profiles WHERE id = ?"
        
        if not profile_id:
             raise ValueError("Profile ID cannot be empty")

        try:
            with self._get_connection() as conn:
                cursor = conn.execute(delete_sql, (profile_id,))
                conn.commit()
            
            if cursor.rowcount == 0:
                # No rows were deleted, meaning the profile ID didn't exist
                self.logger.warning(f"Attempted to delete non-existent profile with ID: {profile_id}")
                raise ProfileNotFoundError(f"Profile with ID '{profile_id}' not found, cannot delete.")
            else:
                self.logger.info(f"Successfully deleted profile with ID: {profile_id}")
                return True
                
        except sqlite3.Error as e:
            self.logger.error(f"Database error while deleting profile ID '{profile_id}': {e}")
            raise ProfileStorageError(f"Failed to delete profile: {e}") from e

    # --- High-Level Save/Load Methods (Task 2.4) ---

    def save_profile(self, profile: AnalysisProfile) -> AnalysisProfile:
        """
        Saves a profile to the database. Handles both creating new profiles
        and updating existing ones based on the profile ID.

        Args:
            profile: The AnalysisProfile object to save.

        Returns:
            The saved AnalysisProfile object (potentially with updated timestamps).

        Raises:
            ValueError: If the profile data is invalid.
            ProfileDuplicateError: If trying to create a profile with a name
                                   that already exists, or if an ID collision occurs.
            ProfileStorageError: If a database error occurs.
        """
        if not profile or not isinstance(profile, AnalysisProfile):
            raise ValueError("Invalid AnalysisProfile object provided.")

        # Ensure ID is set for potential update
        if not profile.id:
            profile.id = str(uuid.uuid4())
            is_new = True
            self.logger.debug(f"Generated new ID for profile: {profile.id}")
        else:
            # Check if ID exists to determine if it's an update or creation attempt with existing ID
            existing_profile = self.get_profile_by_id(str(profile.id)) # Use str() just in case
            is_new = existing_profile is None

        try:
            if is_new:
                self.logger.info(f"Attempting to create new profile with ID: {profile.id}")
                return self.create_profile(profile)
            else:
                self.logger.info(f"Attempting to update existing profile with ID: {profile.id}")
                # Ensure updated_at is managed correctly by update_profile
                # The current implementation of update_profile already handles this
                return self.update_profile(profile)
        except ProfileNotFoundError as e:
            # This might happen in a race condition if the profile was deleted
            # between the get_profile_by_id check and the update_profile call.
            # Or if the initial check failed somehow. Try creating it.
            self.logger.warning(f"Profile {profile.id} not found during update attempt, trying to create instead. Original error: {e}")
            try:
                 return self.create_profile(profile)
            except Exception as create_e:
                 # If create also fails, raise the original or a combined error
                 self.logger.error(f"Failed to create profile {profile.id} after update attempt failed: {create_e}")
                 raise ProfileStorageError(f"Failed to save profile {profile.id}. Update failed and subsequent create failed.") from create_e
        # Let other exceptions (ValueError, ProfileDuplicateError, ProfileStorageError)
        # propagate up from create_profile/update_profile

    def load_profile(self, identifier: str) -> Optional[AnalysisProfile]:
        """
        Loads a profile by its ID or name.

        Tries to interpret the identifier as a UUID first. If it's not a valid UUID
        format or if no profile is found by ID, it attempts to load by name.

        Args:
            identifier: The profile ID (UUID string) or name.

        Returns:
            The found AnalysisProfile object or None if not found.

        Raises:
            ValueError: If the identifier is empty.
            ProfileStorageError: If a database error occurs.
        """
        if not identifier:
            raise ValueError("Identifier (ID or name) cannot be empty")

        profile = None
        # Attempt to load by ID first if it looks like a UUID
        is_potential_uuid = False
        try:
            uuid.UUID(identifier)
            is_potential_uuid = True
        except ValueError:
            pass # Not a valid UUID format

        if is_potential_uuid:
            self.logger.debug(f"Attempting to load profile by ID: {identifier}")
            try:
                profile = self.get_profile_by_id(identifier)
            except ValueError:
                 # Should not happen if uuid.UUID() passed, but handle defensively
                 self.logger.warning(f"get_profile_by_id raised ValueError for seemingly valid UUID: {identifier}")
                 profile = None 
            # Allow ProfileStorageError to propagate

        # If not found by ID or if it wasn't a UUID format, try by name
        if profile is None:
            self.logger.debug(f"Profile not found by ID (or identifier wasn't UUID), attempting to load by name: {identifier}")
            try:
                profile = self.get_profile_by_name(identifier)
            except ValueError as e:
                 # Should only happen if identifier is empty, which is checked above.
                 self.logger.error(f"Unexpected ValueError from get_profile_by_name: {e}")
                 raise # Re-raise unexpected error
            # Allow ProfileStorageError to propagate

        if profile:
            self.logger.info(f"Successfully loaded profile using identifier: {identifier}")
        else:
             self.logger.info(f"No profile found using identifier: {identifier}")

        return profile

    def profile_exists(self, identifier: str) -> bool:
        """
        Checks if a profile exists by ID or name.

        Args:
            identifier: The profile ID (UUID string) or name.

        Returns:
            True if the profile exists, False otherwise.
        """
        try:
            return self.load_profile(identifier) is not None
        except ProfileStorageError:
            # If there's a storage error during the check, assume it doesn't exist
            # or at least is inaccessible. Log the error.
            self.logger.error(f"Storage error occurred while checking existence for identifier '{identifier}'. Returning False.", exc_info=True)
            return False
        except ValueError:
             # Invalid identifier format (e.g., empty string)
             return False

    @handle_db_errors("export_profile_to_json")
    def export_profile_to_json(self, profile_id: str, indent: Optional[int] = 2) -> str:
        """
        Exports a profile to a JSON string.

        Args:
            profile_id: The ID of the profile to export.
            indent: Indentation level for the JSON string. None for compact output.

        Returns:
            A JSON string representation of the profile.

        Raises:
            ProfileNotFoundError: If the profile with the given ID is not found.
            ProfileStorageError: If a database error occurs during loading.
            ValueError: If the profile_id is invalid.
        """
        profile = self.get_profile_by_id(profile_id) # Use direct getter
        if not profile:
            raise ProfileNotFoundError(f"Profile with ID '{profile_id}' not found for export.")
        
        try:
            profile_dict = profile.to_dict()
            # Ensure schema is properly represented as dict if needed
            if isinstance(profile_dict.get('schema_definition'), str):
                 try:
                      profile_dict['schema_definition'] = json.loads(profile_dict['schema_definition'])
                 except json.JSONDecodeError:
                      # Keep as string if it's not valid JSON, maybe log warning
                      self.logger.warning(f"Schema definition for profile {profile_id} is a string but not valid JSON.")

            return json.dumps(profile_dict, indent=indent, default=str) # Use default=str for datetime etc.
        except (TypeError, json.JSONDecodeError) as e:
            self.logger.error(f"Error serializing profile {profile_id} to JSON: {e}")
            raise ProfileStorageError(f"Failed to serialize profile {profile_id} to JSON.") from e

    def import_profile_from_json(self, 
                                 profile_json_string: str, 
                                 generate_new_id: bool = False,
                                 handle_name_conflicts: str = 'rename' # 'rename', 'error', 'overwrite'
                                 ) -> AnalysisProfile:
        """
        Imports a profile from a JSON string representation.

        Args:
            profile_json_string: JSON string of the profile.
            generate_new_id: If True, ignores any existing ID in the JSON 
                             and generates a new one. Defaults to False.
            handle_name_conflicts: Strategy for name conflicts ('rename', 'error', 'overwrite').
                                   Defaults to 'rename'.

        Returns:
            The imported and saved AnalysisProfile object.

        Raises:
            ValueError: If the JSON is invalid or missing required fields.
            ProfileDuplicateError: If handle_name_conflicts='error' and name exists.
            ProfileStorageError: If a database error occurs during saving.
        """
        try:
            profile_dict = json.loads(profile_json_string)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON format: {e}") from e

        # Basic validation of required fields
        required_fields = ['name']
        if not all(field in profile_dict for field in required_fields):
            raise ValueError(f"Missing required fields in JSON: {required_fields}")
            
        # Deserialize using AnalysisProfile.from_dict 
        try:
             profile = AnalysisProfile.from_dict(profile_dict)
        except Exception as e:
             # Catch potential errors during deserialization (e.g., bad date format)
             raise ValueError(f"Failed to deserialize profile from dictionary: {e}") from e

        # Handle ID generation
        original_id = profile.id
        if generate_new_id or not original_id:
            profile.id = str(uuid.uuid4())
            self.logger.info(f"Generated new ID {profile.id} for imported profile '{profile.name}'.")
        elif not isinstance(original_id, str): # Ensure ID from JSON is stringified if needed
             profile.id = str(original_id)

        # Handle name conflicts
        existing_by_name = self.get_profile_by_name(profile.name)
        
        if existing_by_name and str(existing_by_name.id) != str(profile.id):
            if handle_name_conflicts == 'error':
                raise ProfileDuplicateError(f"Profile name '{profile.name}' already exists (ID: {existing_by_name.id}). Set handle_name_conflicts strategy.")
            elif handle_name_conflicts == 'overwrite':
                self.logger.warning(f"Overwriting existing profile with name '{profile.name}' (ID: {existing_by_name.id}) due to import setting.")
                try:
                    self.delete_profile(str(existing_by_name.id))
                except ProfileNotFoundError:
                    pass # Ignore if it was already deleted somehow
                except ProfileStorageError as e:
                     raise ProfileStorageError(f"Failed to delete existing profile {existing_by_name.id} before overwrite.") from e
            elif handle_name_conflicts == 'rename':
                base_name = profile.name
                counter = 1
                while self.get_profile_by_name(f"{base_name} ({counter})"):
                    counter += 1
                profile.name = f"{base_name} ({counter})"
                self.logger.info(f"Renamed imported profile to '{profile.name}' due to name conflict.")
            else:
                 raise ValueError(f"Invalid handle_name_conflicts strategy: {handle_name_conflicts}")
                
        # Ensure timestamps are set correctly (from_dict should handle defaults)
        now = datetime.now(timezone.utc)
        profile.created_at = profile.created_at or now # Keep original if present, else set now
        profile.updated_at = now # Always set updated_at to now on import/save

        # Save the potentially modified profile
        # save_profile handles create vs update logic
        try:
            saved_profile = self.save_profile(profile)
            return saved_profile
        except ProfileDuplicateError as e:
             # This might happen if generate_new_id=False and the ID already exists
             # Or if the name conflict resolution still resulted in an issue (e.g., race condition)
             self.logger.error(f"Duplicate error during final save in import: {e}")
             raise ProfileDuplicateError(f"Failed to save imported profile due to conflict: {e}") from e
        # Let other save_profile errors propagate

    def save_profiles_batch(self, profiles: List[AnalysisProfile]) -> Tuple[List[AnalysisProfile], List[Dict[str, Any]]]:
        """
        Saves a batch of profiles, attempting to save each one individually.
        Uses the save_profile method which handles create/update logic.

        Args:
            profiles: A list of AnalysisProfile objects to save.

        Returns:
            A tuple containing:
            - List[AnalysisProfile]: The list of successfully saved profiles.
            - List[Dict[str, Any]]: A list of errors encountered, where each
              dict contains 'index' and 'error' (exception object).
        """
        results: List[AnalysisProfile] = []
        errors: List[Dict[str, Any]] = []

        if not profiles:
            return [], []

        for index, profile in enumerate(profiles):
            try:
                saved_profile = self.save_profile(profile)
                results.append(saved_profile)
            except (ValueError, ProfileDuplicateError, ProfileStorageError) as e:
                self.logger.error(f"Error saving profile at batch index {index} (Name: {getattr(profile, 'name', 'N/A')}): {e}")
                errors.append({"index": index, "error": e})
            except Exception as e:
                 # Catch unexpected errors
                 self.logger.error(f"Unexpected error saving profile at batch index {index} (Name: {getattr(profile, 'name', 'N/A')}): {e}", exc_info=True)
                 errors.append({"index": index, "error": e})

        self.logger.info(f"Batch save completed. Success: {len(results)}, Failures: {len(errors)}")
        return results, errors

    # --- Health Check --- 
    def perform_storage_health_check(self) -> Dict[str, Any]:
        """Performs diagnostic checks on the storage system (database and backups)."""
        results = {
            "status": "healthy", # healthy, degraded, unhealthy
            "issues": [],
            "checks_performed": []
        }
        
        # 1. Check Database Connection
        check_name = "Database Connection"
        results["checks_performed"].append(check_name)
        try:
            # Use a context manager to ensure connection is closed
            with self._get_connection() as conn:
                 # Optionally perform a simple query
                 conn.execute("SELECT 1")
            self.logger.info(f"Health Check: {check_name} successful.")
        except ProfileStorageError as e: # Catch errors from _get_connection
            results["status"] = "unhealthy"
            issue_msg = f"{check_name} Failed: {e}"
            results["issues"].append(issue_msg)
            self.logger.error(f"Health Check: {issue_msg}")
            # If connection fails, cannot perform further DB checks
            return results 

        # 2. Check Database Integrity
        check_name = "Database Integrity"
        results["checks_performed"].append(check_name)
        try:
            with self._get_connection() as conn:
                cursor = conn.execute("PRAGMA integrity_check;")
                integrity_result = cursor.fetchone()
                if integrity_result is None or integrity_result[0].lower() != 'ok':
                    results["status"] = "unhealthy"
                    issue_msg = f'{check_name} Failed: PRAGMA integrity_check returned \'{integrity_result[0] if integrity_result else "No result"}\'. Database might be corrupt.'
                    results["issues"].append(issue_msg)
                    self.logger.error(f"Health Check: {issue_msg}")
                else:
                     self.logger.info(f"Health Check: {check_name} successful ('{integrity_result[0]}').")
        except sqlite3.Error as e:
            # Catch potential errors during PRAGMA execution itself
            results["status"] = "unhealthy"
            issue_msg = f"{check_name} Check Execution Failed: {e}"
            results["issues"].append(issue_msg)
            self.logger.error(f"Health Check: {issue_msg}", exc_info=True)
        except ProfileStorageError as e: # Catch connection errors again if they happen here
            results["status"] = "unhealthy"
            issue_msg = f"{check_name} Check Failed due to connection error: {e}"
            results["issues"].append(issue_msg)
            self.logger.error(f"Health Check: {issue_msg}")
            

        # 3. Check Backup Directory Existence (Basic Check)
        check_name = "Backup Directory"
        results["checks_performed"].append(check_name)
        try:
            db_dir = os.path.dirname(self.db_path)
            backup_dir = os.path.join(db_dir, "backups") # Assumed relative path
            if not os.path.exists(backup_dir) or not os.path.isdir(backup_dir):
                # Degraded status if backups seem missing, not fully unhealthy yet
                if results["status"] == "healthy": 
                     results["status"] = "degraded"
                issue_msg = f'{check_name} Check Failed: Expected backup directory not found at \'{backup_dir}\'.'
                results["issues"].append(issue_msg)
                self.logger.warning(f"Health Check: {issue_msg}")
            else:
                 self.logger.info(f"Health Check: {check_name} successful (Directory exists at '{backup_dir}').")
        except Exception as e:
            # Catch potential OS errors during path checks
            if results["status"] == "healthy":
                 results["status"] = "degraded"
            issue_msg = f"{check_name} Check Failed with OS error: {e}"
            results["issues"].append(issue_msg)
            self.logger.error(f"Health Check: {issue_msg}", exc_info=True)

        self.logger.info(f"Storage health check completed with status: {results['status']}")
        return results


# --- Example Usage (Optional) ---
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    repo = ProfileRepository() 
    
    # Example: Create a profile (implement create_profile first)
    # new_profile = AnalysisProfile(name="Test Profile", instructions="Test instructions.")
    # try:
    #     created = repo.create_profile(new_profile)
    #     print(f"Created profile: {created.id} - {created.name}")
    # except ProfileDuplicateError as e:
    #     print(f"Error: {e}")
    # except ProfileStorageError as e:
    #     print(f"Storage Error: {e}")

    # Example: List profiles (implement get_all_profiles first)
    # try:
    #    all_profiles = repo.get_all_profiles()
    #    print(f"Found {len(all_profiles)} profiles:")
    #    for p in all_profiles:
    #        print(f"- {p.id} | {p.name}")
    # except ProfileStorageError as e:
    #    print(f"Storage Error: {e}")

    print("ProfileRepository initialized.") 