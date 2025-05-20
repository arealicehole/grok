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

# Import the actual AnalysisProfile model
from .models.analysis_profile import AnalysisProfile

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
        """Ensures the 'profiles' table exists and has the necessary columns (including 'order')."""
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS profiles (
            id TEXT PRIMARY KEY NOT NULL,
            name TEXT UNIQUE NOT NULL,
            instructions TEXT,
            schema_definition TEXT NOT NULL, -- Stored as string
            "order" INTEGER,                 -- Added order column
            created_at TEXT NOT NULL,        -- ISO format string
            updated_at TEXT NOT NULL,         -- ISO format string
            last_used_timestamp TEXT,        -- ISO format string, NULLABLE
            usage_count INTEGER DEFAULT 0    -- Default to 0, NOT NULL
        );
        """
        # Add UNIQUE constraint for ID if not using AUTOINCREMENT
        # create_id_index_sql = "CREATE UNIQUE INDEX IF NOT EXISTS idx_profiles_id ON profiles(id);"
        create_name_index_sql = "CREATE UNIQUE INDEX IF NOT EXISTS idx_profiles_name ON profiles(name);"
        create_updated_at_index_sql = "CREATE INDEX IF NOT EXISTS idx_profiles_updated_at ON profiles(updated_at);"
        # Don't create order index here yet
        
        with self._get_connection() as conn:
            conn.execute(create_table_sql)
            # conn.execute(create_id_index_sql) # Only if ID is not PRIMARY KEY AUTOINCREMENT
            conn.execute(create_name_index_sql)
            conn.execute(create_updated_at_index_sql)
            # conn.execute(create_order_index_sql) # Moved below
            
            # --- Check and add 'order' column if missing --- 
            cursor = conn.execute("PRAGMA table_info(profiles);")
            columns = [column['name'] for column in cursor.fetchall()]
            
            if 'order' not in columns:
                self.logger.info("Adding missing 'order' column to 'profiles' table.")
                conn.execute('ALTER TABLE profiles ADD COLUMN "order" INTEGER;')
                # Also create the index now that the column exists
                conn.execute("CREATE INDEX IF NOT EXISTS idx_profiles_order ON profiles(\"order\");")
            # --- End check ---
            
            # --- Check and add 'last_used_timestamp' and 'usage_count' columns if missing ---
            if 'last_used_timestamp' not in columns:
                self.logger.info("Adding missing 'last_used_timestamp' column to 'profiles' table.")
                conn.execute('ALTER TABLE profiles ADD COLUMN last_used_timestamp TEXT;')
            if 'usage_count' not in columns:
                self.logger.info("Adding missing 'usage_count' column to 'profiles' table.")
                conn.execute('ALTER TABLE profiles ADD COLUMN usage_count INTEGER DEFAULT 0;')
            # --- End check ---
            
            conn.commit()
        # Updated log message
        self.logger.info(f"Ensured 'profiles' table exists and includes 'order', 'last_used_timestamp', and 'usage_count' columns in {self.db_path}")

    def _serialize_profile(self, profile: AnalysisProfile) -> Tuple[Optional[str], str, Optional[str], str, Optional[int], str, str, Optional[str], int]:
        """Converts an AnalysisProfile object into a tuple for database insertion/update."""
        if not isinstance(profile, AnalysisProfile):
             raise TypeError("Input must be an AnalysisProfile object")
        
        # Timestamps are already ISO strings in the model
        created_at_iso = profile.created_at
        updated_at_iso = profile.updated_at
        last_used_ts_iso = profile.last_used_timestamp # This is already Optional[str]
        
        # Schema definition is already a string
        schema_def_str = profile.schema_definition or ""

        return (
            str(profile.id) if profile.id else None, # ID is string UUID
            profile.name,
            profile.instructions,
            schema_def_str, # Use the string directly
            profile.order, # Include order (Optional[int])
            created_at_iso,
            updated_at_iso,
            last_used_ts_iso,
            profile.usage_count
        )

    def _deserialize_profile(self, row: sqlite3.Row) -> AnalysisProfile:
        """Converts a database row (sqlite3.Row) into an AnalysisProfile object."""
        if not isinstance(row, sqlite3.Row):
             raise TypeError("Input must be a sqlite3.Row object")
             
        # --- ADD LOGGING FOR RAW ID --- 
        raw_id = row["id"]
        self.logger.debug(f"_deserialize_profile: Raw row['id'] = {repr(raw_id)}, Type = {type(raw_id)}")
        # ------------------------------
        
        profile_id = row["id"] # Get ID for logging context
        try:
            # Schema definition is stored as string
            schema_def = row["schema_definition"] or ""
        except Exception as e: # Catch unexpected errors during deserialization
            self.logger.error(f"Unexpected error deserializing schema for profile ID {profile_id}: {e}", exc_info=True)
            raise ProfileStorageError(f"Failed to deserialize profile {profile_id}") from e

        # Timestamps are stored as ISO strings
        created_at_iso = row["created_at"]
        updated_at_iso = row["updated_at"]

        # Get order, could be None
        profile_order = row["order"]

        # Get last_used_timestamp and usage_count, could be None/default
        last_used_ts = row["last_used_timestamp"] if "last_used_timestamp" in row.keys() else None
        usage_count = row["usage_count"] if "usage_count" in row.keys() else 0

        if not created_at_iso or not updated_at_iso:
             self.logger.error(f"Missing timestamp data for profile ID {profile_id}")
             raise ProfileCorruptionError(f"Missing timestamp data for profile {profile_id}. Data may be corrupt.")

        return AnalysisProfile(
            id=profile_id, # ID is now INTEGER
            name=row["name"],
            instructions=row["instructions"],
            schema_definition=schema_def, # Use the string directly
            order=profile_order, # Assign order
            created_at=created_at_iso, # Use ISO string
            updated_at=updated_at_iso, # Use ISO string
            last_used_timestamp=last_used_ts,
            usage_count=usage_count
        )

    # --- Validation Orchestrator ---
    def _validate_profile_data(self, profile: AnalysisProfile, is_update: bool = False) -> ValidationResult:
        """Runs all validations for an Analysis Profile instance."""
        full_result = ValidationResult()

        # Check name uniqueness using get_profile_by_name
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

    @handle_db_errors("get_max_order")
    def _get_max_order(self) -> int:
        """Gets the maximum order value from the profiles table."""
        query = "SELECT MAX(\"order\") FROM profiles"
        with self._get_connection() as conn:
            cursor = conn.execute(query)
            result = cursor.fetchone()
            return result[0] if result and result[0] is not None else -1

    @handle_db_errors("create_profile")
    def create_profile(self, profile: AnalysisProfile) -> AnalysisProfile:
        """
        Creates a new profile in the database.
        Ensures a unique ID is assigned if not provided.
        Sets created_at and updated_at timestamps.
        The 'order' field is set to the next available order value.
        Sets last_used_timestamp to None and usage_count to 0 initially.
        """
        validation_result = self._validate_profile_data(profile, is_update=False)
        if not validation_result.is_valid:
            self.logger.error(f"Validation failed for creating profile '{profile.name}': {validation_result.errors_to_string()}")
            raise ProfileValidationError(f"Validation failed: {validation_result.errors_to_string()}")

        # Ensure ID is a string (UUID)
        if profile.id is None: # Should be if it's truly new
            profile.id = str(uuid.uuid4())
        elif not isinstance(profile.id, str):
             profile.id = str(profile.id)

        now_iso = datetime.now(timezone.utc).isoformat()
        profile.created_at = now_iso
        profile.updated_at = now_iso
        
        # Initialize last_used_timestamp and usage_count for new profiles
        profile.last_used_timestamp = None
        profile.usage_count = 0

        # Assign order if not explicitly set
        if profile.order is None:
            max_order = self._get_max_order()
            profile.order = max_order + 1
        
        # ID from AnalysisProfile is int, but stored as TEXT in DB
        # Convert to string for query if it's int
        profile_id_str = str(profile.id) if isinstance(profile.id, int) else profile.id

        sql = """
        INSERT INTO profiles (id, name, instructions, schema_definition, "order", created_at, updated_at, last_used_timestamp, usage_count)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
        """
        
        serialized_values = self._serialize_profile(profile)
        # Ensure the ID in serialized_values is the string version we determined
        final_serialized_values = (profile_id_str,) + serialized_values[1:]

        with self._get_connection() as conn:
            try:
                conn.execute(sql, final_serialized_values)
                conn.commit()
                self.logger.info(f"Profile '{profile.name}' (ID: {profile.id}) created successfully with order {profile.order}.")
                return profile 
            except sqlite3.IntegrityError as e:
                conn.rollback()
                # This primarily catches UNIQUE constraint violations (name, id)
                self.logger.error(f"Failed to create profile '{profile.name}' due to integrity error: {e}", exc_info=False) # exc_info=False for cleaner log
                if "UNIQUE constraint failed: profiles.name" in str(e):
                    raise ProfileValidationError(f"Profile name '{profile.name}' already exists.")
                elif "UNIQUE constraint failed: profiles.id" in str(e): # Less likely if UUIDs are used correctly
                    raise ProfileDatabaseError(f"Profile ID '{profile.id}' already exists. This should not happen with UUIDs.")
                else:
                    raise ProfileDatabaseError(f"Database integrity error for profile '{profile.name}': {e}") from e
            except Exception as e: # Catch other potential errors during execution or commit
                conn.rollback()
                self.logger.error(f"An unexpected error occurred creating profile '{profile.name}': {e}", exc_info=True)
                raise ProfileStorageError(f"Could not create profile '{profile.name}'.") from e

    @handle_db_errors("get_profile_by_id")
    def get_profile_by_id(self, profile_id_str: str) -> Optional[AnalysisProfile]:
        """Retrieves a profile by its unique ID (UUID string)."""
        select_sql = "SELECT * FROM profiles WHERE id = ?"
        
        # Validate if the input string is a valid UUID format
        try:
            uuid.UUID(profile_id_str)
        except ValueError:
            raise ValueError(f"Invalid UUID format for profile ID: '{profile_id_str}'")

        try:
            with self._get_connection() as conn:
                cursor = conn.execute(select_sql, (profile_id_str,))
                row = cursor.fetchone()
            
            if row:
                self.logger.debug(f"Retrieved profile by ID: {profile_id_str}")
                return self._deserialize_profile(row)
            else:
                self.logger.debug(f"No profile found with ID: {profile_id_str}")
                # Raise not found instead of returning None for get_by_id
                raise ProfileNotFoundError(f"Profile with ID {profile_id_str} not found.")
        except sqlite3.Error as e:
            self.logger.error(f"Database error while retrieving profile by ID {profile_id_str}: {e}")
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
    def get_all_profiles(self, filters: Optional[Dict] = None, page: int = 1, page_size: int = 20, sort_by: str = 'order', sort_order: str = 'ASC') -> List[AnalysisProfile]:
        """
        Retrieves a list of profiles, supporting filtering, pagination, and sorting.

        Args:
            filters: Optional dictionary for filtering profiles.
                     Supported filters: 'name' (partial match), 'created_after' (ISO date string)
            page: Page number for pagination (1-indexed).
            page_size: Number of profiles per page.
            sort_by: Field to sort by (e.g., 'name', 'created_at', 'updated_at', 'order'). Default 'order'.
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
        allowed_sort_fields = ['name', 'created_at', 'updated_at', 'order'] # Added 'order'
        sort_field_sql = '"order"' if sort_by == 'order' else sort_by # Quote 'order'
        
        if sort_by not in allowed_sort_fields:
            self.logger.warning(f"Invalid sort_by field: {sort_by}. Defaulting to 'order'.")
            sort_field_sql = '"order"'
            
        order = 'ASC' if sort_order.upper() == 'ASC' else 'DESC' # Default to ASC if invalid
        query += f" ORDER BY {sort_field_sql} {order}" 

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
                except (TypeError, json.JSONDecodeError, ValueError, ProfileCorruptionError) as deser_error:
                     # Log error for the specific row but continue processing others
                     self.logger.error(f"Failed to deserialize profile row ID {row.get('id', 'N/A')}: {deser_error}")
                     # Optionally, you could add a placeholder or skip the problematic row

            self.logger.info(f"Retrieved {len(profiles)} profiles (Page {page}, Size {page_size}) with filters: {filters}, sorted by {sort_field_sql} {order}")
            return profiles
        except sqlite3.Error as e:
            self.logger.error(f"Database error while retrieving profiles: {e}")
            raise ProfileStorageError(f"Failed to retrieve profiles: {e}") from e

    @handle_db_errors("update_profile")
    def update_profile(self, profile: AnalysisProfile) -> AnalysisProfile:
        """Updates an existing profile in the database. ID must be set."""
        if profile.id is None:
            self.logger.error("Attempted to update profile with no ID.")
            raise ProfileValidationError("Profile ID is required for an update.")

        # Validate before updating
        validation_result = self._validate_profile_data(profile, is_update=True)
        if not validation_result.is_valid:
            self.logger.error(f"Validation failed for updating profile ID '{profile.id}': {validation_result.errors_to_string()}")
            raise ProfileValidationError(f"Validation failed: {validation_result.errors_to_string()}")
        
        profile.updated_at = datetime.now(timezone.utc).isoformat()
        
        # Ensure ID is string for query
        profile_id_str = str(profile.id) if isinstance(profile.id, int) else profile.id

        sql = """
        UPDATE profiles 
        SET name = ?, instructions = ?, schema_definition = ?, "order" = ?, created_at = ?, updated_at = ?, last_used_timestamp = ?, usage_count = ?
        WHERE id = ?;
        """
        
        # _serialize_profile returns ID as first element, but we need it last for WHERE clause
        serialized_tuple = self._serialize_profile(profile)
        # (id, name, instructions, schema, order, created_at, updated_at, last_used_ts, usage_count)
        # We need: (name, instructions, schema, order, created_at, updated_at, last_used_ts, usage_count, id)
        
        params_for_update = serialized_tuple[1:] + (profile_id_str,)

        with self._get_connection() as conn:
            try:
                cursor = conn.execute(sql, params_for_update)
                conn.commit()
                
                if cursor.rowcount == 0:
                    self.logger.warning(f"Attempted to update profile ID '{profile.id}', but no rows were affected (profile not found).")
                    raise ProfileNotFoundError(f"Profile with ID '{profile.id}' not found for update.")
                
                self.logger.info(f"Profile '{profile.name}' (ID: {profile.id}) updated successfully.")
                return profile
            except sqlite3.IntegrityError as e:
                conn.rollback()
                self.logger.error(f"Integrity error updating profile ID '{profile.id}': {e}", exc_info=False)
                if "UNIQUE constraint failed: profiles.name" in str(e):
                    raise ProfileValidationError(f"Profile name '{profile.name}' already exists (conflict with another profile).")
                else:
                    raise ProfileDatabaseError(f"Database integrity error updating profile '{profile.name}': {e}") from e
            except Exception as e:
                conn.rollback()
                self.logger.error(f"An unexpected error occurred updating profile ID '{profile.id}': {e}", exc_info=True)
                raise ProfileStorageError(f"Could not update profile '{profile.name}'.") from e

    @handle_db_errors("delete_profile")
    def delete_profile(self, profile_id_str: str) -> bool:
        """Deletes a profile by its ID. ID should be a string."""
        delete_sql = "DELETE FROM profiles WHERE id = ?"
        
        # Validate UUID format
        try:
            uuid.UUID(profile_id_str)
        except ValueError:
            raise ValueError(f"Invalid UUID format for profile ID: '{profile_id_str}'")

        try:
            with self._get_connection() as conn:
                cursor = conn.execute(delete_sql, (profile_id_str,))
                conn.commit()
            
            if cursor.rowcount == 0:
                # No rows deleted
                self.logger.warning(f"Attempted to delete non-existent profile with ID: {profile_id_str}")
                raise ProfileNotFoundError(f"Profile with ID {profile_id_str} not found, cannot delete.")
            else:
                self.logger.info(f"Successfully deleted profile with ID: {profile_id_str}")
                return True
                
        except sqlite3.Error as e:
            self.logger.error(f"Database error while deleting profile ID {profile_id_str}: {e}")
            raise ProfileStorageError(f"Failed to delete profile: {e}") from e

    @handle_db_errors("update_profiles_order")
    def update_profiles_order(self, updates: List[Tuple[int, int]]) -> bool:
        """ 
        Updates the order for multiple profiles in a single transaction.

        Args:
            updates: A list of tuples, where each tuple is (profile_id, new_order).

        Returns:
            True if the update was successful, False otherwise.
            
        Raises:
            ValueError: If the updates list is empty or contains invalid data.
            ProfileStorageError: If a database error occurs.
        """
        if not updates:
            self.logger.warning("update_profiles_order called with empty updates list.")
            return True # Nothing to do, technically successful
            
        update_sql = "UPDATE profiles SET \"order\" = ? WHERE id = ?"
        update_params = []
        
        # Validate input data structure
        for item in updates:
            is_valid_format = False
            if isinstance(item, tuple) and len(item) == 2 and isinstance(item[1], int):
                try:
                    # Check if the first element is a valid UUID string
                    uuid.UUID(str(item[0]))
                    is_valid_format = True
                except ValueError:
                    pass # Not a valid UUID string

            if not is_valid_format:
                self.logger.error(f"Invalid update item format detected: {item}")
                raise ValueError("Invalid update item format. Expected list of (valid_uuid_string_id, int_order) tuples.")

            update_params.append((item[1], item[0])) # SQL needs (order, id)
        
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor() # Get a cursor for executemany
                # Execute updates in a transaction
                cursor.executemany(update_sql, update_params)
                updated_rows = cursor.rowcount
                conn.commit()
            
            if updated_rows != len(updates):
                 self.logger.warning(f"Expected to update {len(updates)} profiles order, but affected {updated_rows} rows. Some IDs might not exist.")
                 # Decide if this is a partial success or failure. Let's consider it potentially problematic.
                 # Returning False might be safer, or raise a specific warning/error.
                 # For now, log warning and return True assuming non-existent IDs are acceptable.
                 
            self.logger.info(f"Successfully updated order for {updated_rows} profiles.")
            return True
            
        except sqlite3.Error as e:
            self.logger.error(f"Database error while updating profile orders: {e}", exc_info=True)
            raise ProfileStorageError(f"Failed to update profile orders: {e}") from e
        except Exception as e:
             self.logger.error(f"Unexpected error during profile order update: {e}", exc_info=True)
             raise

    # --- High-Level Save/Load Methods (Task 2.4) ---

    def save_profile(self, profile: AnalysisProfile) -> AnalysisProfile:
        """
        Saves a profile to the database. Handles creating new profiles (with auto ID and order)
        and updating existing ones based on the profile ID.

        Args:
            profile: The AnalysisProfile object to save.

        Returns:
            The saved AnalysisProfile object (with assigned ID/order if new, updated timestamps).

        Raises:
            ValueError: If the profile object is invalid or if trying to update without a valid ID.
            ProfileDuplicateError: If trying to create a profile with a name that already exists.
            ProfileNotFoundError: If trying to update a profile ID that doesn't exist.
            ProfileStorageError: If a database error occurs.
            ProfileValidationError: If validation fails.
        """
        if not profile or not isinstance(profile, AnalysisProfile):
            raise ValueError("Invalid AnalysisProfile object provided.")

        # Determine if it's a new profile (ID is None or not a UUID string)
        # The AnalysisProfile constructor should have already assigned a UUID if id was None.
        # We rely on update_profile to raise ProfileNotFoundError if the ID doesn't exist.
        is_new = not isinstance(profile.id, uuid.UUID)

        # The AnalysisProfile model ensures profile.id is a UUID.
        # We pass it directly to create_profile or update_profile.
        if is_new: # Should generally not happen if constructor is used correctly
            self.logger.warning(f"save_profile called with a non-UUID ID: {profile.id}. Attempting create.")
            # Ensure ID is a UUID before creating
            if not profile.id:
                profile.id = uuid.uuid4()
            elif not isinstance(profile.id, uuid.UUID):
                 # Attempt to convert if it's a string, otherwise generate new
                 try:
                     profile.id = uuid.UUID(str(profile.id))
                 except ValueError:
                     profile.id = uuid.uuid4()
            return self.create_profile(profile) # create_profile uses profile.id
        else:
             # ID is present and assumed to be a valid UUID for update
             if not isinstance(profile.id, uuid.UUID):
                 # Defensive check if ID is somehow not a UUID
                 raise ValueError(f"Profile ID for update must be a UUID, got: {type(profile.id)}")
             self.logger.info(f"Attempting to update existing profile with ID: {profile.id}")
             # Order should be provided for update, otherwise it retains existing value (if DB schema allows NULL)
             # or causes error if DB schema requires NOT NULL and it wasn't loaded.
             # Current update logic requires all fields to be set.
             return self.update_profile(profile)
        
        # Note: The previous try/except block handling ProfileNotFoundError during update 
        #       is removed. The update_profile now raises ProfileNotFoundError directly if needed,
        #       and create_profile handles its own errors.

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

    @handle_db_errors("record_profile_usage")
    def record_profile_usage(self, profile_id_str: str) -> bool:
        """
        Records that a profile has been used. Updates its last_used_timestamp and increments usage_count.
        Args:
            profile_id_str: The string ID of the profile to update.
        Returns:
            True if successful, False otherwise.
        Raises:
            ProfileNotFoundError if the profile doesn't exist.
            ProfileStorageError for other database issues.
        """
        self.logger.debug(f"Attempting to record usage for profile ID: {profile_id_str}")
        
        # Fetch the profile first to ensure it exists and to get current usage_count
        # This also ensures we are not modifying a non-existent profile directly with SQL
        try:
            profile = self.get_profile_by_id(profile_id_str) # get_profile_by_id expects string
        except ProfileNotFoundError: # Let get_profile_by_id handle the specific not found error
            self.logger.warning(f"Cannot record usage: Profile with ID '{profile_id_str}' not found.")
            raise # Re-raise the ProfileNotFoundError
        
        if profile is None: # Should be caught by above, but as a safeguard
             self.logger.warning(f"Profile with ID '{profile_id_str}' was unexpectedly None after fetch in record_profile_usage.")
             raise ProfileNotFoundError(f"Profile with ID '{profile_id_str}' not found.")

        profile.last_used_timestamp = datetime.now(timezone.utc).isoformat()
        profile.usage_count = (profile.usage_count or 0) + 1 # Ensure usage_count is not None
        profile.updated_at = datetime.now(timezone.utc).isoformat() # Also update the general updated_at

        # Use the existing update_profile method to save changes
        # This re-uses validation and robust saving logic
        try:
            self.update_profile(profile)
            self.logger.info(f"Successfully recorded usage for profile ID '{profile_id_str}'. New usage_count: {profile.usage_count}, Last_used: {profile.last_used_timestamp}")
            return True
        except (ProfileNotFoundError, ProfileValidationError, ProfileStorageError) as e: # Catch errors from update_profile
            self.logger.error(f"Failed to update profile '{profile_id_str}' while recording usage: {e}", exc_info=True)
            # Re-raise the specific error from update_profile if needed or a general one
            raise ProfileStorageError(f"Failed to record usage for profile ID '{profile_id_str}'.") from e
        return False # Should not be reached if exceptions are raised


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