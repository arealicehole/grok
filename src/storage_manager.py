# src/storage_manager.py
import sqlite3
import logging
import os
import json
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime

# Assuming AnalysisProfile model is defined in models.py
# from .models import AnalysisProfile 
# Placeholder until models.py is created or updated
class AnalysisProfile:
    # Minimal placeholder for type hinting
    def __init__(self, id: str, name: str, instructions: str, schema_definition: dict, created_at: datetime, updated_at: datetime):
        self.id = id
        self.name = name
        self.instructions = instructions
        self.schema_definition = schema_definition
        self.created_at = created_at
        self.updated_at = updated_at

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
        # Basic reconstruction for now
        return cls(
            id=data['id'],
            name=data['name'],
            instructions=data.get('instructions', ''),
            schema_definition=data.get('schema_definition', {}),
            created_at=datetime.fromisoformat(data['created_at']) if data.get('created_at') else datetime.utcnow(),
            updated_at=datetime.fromisoformat(data['updated_at']) if data.get('updated_at') else datetime.utcnow()
        )

from .storage_interface import StorageInterface
from config.settings import DATABASE_PATH

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class SQLiteStorage(StorageInterface):
    """SQLite implementation for Analysis Profile storage."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or DATABASE_PATH
        self.conn: Optional[sqlite3.Connection] = None
        logger.info(f"Initializing SQLite storage at: {self.db_path}")
        self._ensure_db_directory()
        self.initialize()

    def _ensure_db_directory(self):
        """Ensure the directory for the database file exists."""
        try:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            logger.debug(f"Ensured directory exists: {self.db_path.parent}")
        except Exception as e:
            logger.error(f"Failed to create database directory {self.db_path.parent}: {e}")
            raise

    def _get_connection(self) -> sqlite3.Connection:
        """Establish and return a database connection."""
        if self.conn is None or self._is_connection_closed():
            try:
                self.conn = sqlite3.connect(self.db_path, detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
                self.conn.row_factory = sqlite3.Row # Return rows as dict-like objects
                self.conn.execute("PRAGMA foreign_keys = ON;") # Enforce foreign keys if used later
                self.conn.execute("PRAGMA journal_mode=WAL;") # Use WAL for better concurrency
                logger.info(f"Database connection established: {self.db_path}")
            except sqlite3.Error as e:
                logger.error(f"Failed to connect to database {self.db_path}: {e}")
                raise
        return self.conn

    def _is_connection_closed(self) -> bool:
        """Check if the connection is closed or unusable."""
        if self.conn is None:
            return True
        try:
            # Try a simple query to check if the connection is alive
            self.conn.execute("SELECT 1")
            return False
        except sqlite3.ProgrammingError as e:
            # ProgrammingError: SQLite objects created in a thread can only be used in that same thread.
            # The object was created in thread id X and this is thread id Y.
            # This can happen if the connection object is shared across threads without proper handling.
            # For now, we assume this means the connection is effectively closed for this thread.
            logger.warning(f"Connection object likely unusable in current thread: {e}")
            return True
        except sqlite3.Error:
            # Other SQLite errors likely mean the connection is closed.
            return True

    def initialize(self) -> None:
        """Initialize the database and create tables if they don't exist."""
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS profiles (
            id TEXT PRIMARY KEY,
            name TEXT UNIQUE NOT NULL,
            instructions TEXT,
            schema_definition TEXT NOT NULL, -- Storing as JSON text
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        """
        create_name_index_sql = "CREATE UNIQUE INDEX IF NOT EXISTS idx_profiles_name ON profiles(name);"
        create_updated_at_index_sql = "CREATE INDEX IF NOT EXISTS idx_profiles_updated_at ON profiles(updated_at);"
        
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute(create_table_sql)
            cursor.execute(create_name_index_sql)
            cursor.execute(create_updated_at_index_sql)
            conn.commit()
            logger.info("Database initialized successfully.")
        except sqlite3.Error as e:
            logger.error(f"Database initialization failed: {e}")
            # Attempt to close connection if initialization fails
            self.close()
            raise
            
    # --- CRUD Method Placeholders (To be implemented in task 2.3) --- 

    def save_profile(self, profile: AnalysisProfile) -> bool:
        logger.warning("save_profile not fully implemented yet.")
        # Placeholder: Implementation will involve INSERT or UPDATE
        # Need to handle serialization (profile object to DB row)
        # Need transaction management and error handling
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            # Example (needs proper implementation)
            # serialized_data = self._serialize_profile(profile)
            # cursor.execute("INSERT OR REPLACE INTO profiles (...) VALUES (...)", serialized_data)
            # conn.commit()
            logger.info(f"Placeholder save for profile: {profile.name}")
            return True # Placeholder return
        except sqlite3.Error as e:
            logger.error(f"Failed to save profile {profile.name}: {e}")
            # Consider rolling back if in a transaction
            return False

    def get_profile_by_id(self, profile_id: str) -> Optional[AnalysisProfile]:
        logger.warning(f"get_profile_by_id not fully implemented yet.")
        # Placeholder: Implementation will involve SELECT WHERE id = ?
        # Need to handle deserialization (DB row to profile object)
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            # cursor.execute("SELECT * FROM profiles WHERE id = ?", (profile_id,))
            # row = cursor.fetchone()
            # if row:
            #    return self._deserialize_profile(row)
            return None # Placeholder return
        except sqlite3.Error as e:
            logger.error(f"Failed to get profile by id {profile_id}: {e}")
            return None

    def get_profile_by_name(self, name: str) -> Optional[AnalysisProfile]:
        logger.warning(f"get_profile_by_name not fully implemented yet.")
        # Placeholder: Implementation will involve SELECT WHERE name = ?
        # Need to handle deserialization
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            # cursor.execute("SELECT * FROM profiles WHERE name = ?", (name,))
            # row = cursor.fetchone()
            # if row:
            #     return self._deserialize_profile(row)
            return None # Placeholder return
        except sqlite3.Error as e:
            logger.error(f"Failed to get profile by name {name}: {e}")
            return None

    def list_profiles(self, filters: Optional[Dict[str, Any]] = None) -> List[AnalysisProfile]:
        logger.warning(f"list_profiles not fully implemented yet.")
        # Placeholder: Implementation will involve SELECT with optional WHERE clauses
        # Need to handle deserialization for multiple rows
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            # query = "SELECT * FROM profiles"
            # params = []
            # if filters: # Add WHERE clauses based on filters
            #    ...
            # cursor.execute(query, params)
            # rows = cursor.fetchall()
            # return [self._deserialize_profile(row) for row in rows]
            return [] # Placeholder return
        except sqlite3.Error as e:
            logger.error(f"Failed to list profiles: {e}")
            return []

    def delete_profile(self, profile_id: str) -> bool:
        logger.warning(f"delete_profile not fully implemented yet.")
        # Placeholder: Implementation will involve DELETE WHERE id = ?
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            # cursor.execute("DELETE FROM profiles WHERE id = ?", (profile_id,))
            # conn.commit()
            # return cursor.rowcount > 0 # Check if a row was actually deleted
            logger.info(f"Placeholder delete for profile ID: {profile_id}")
            return True # Placeholder return
        except sqlite3.Error as e:
            logger.error(f"Failed to delete profile {profile_id}: {e}")
            return False
            
    # --- Helper Methods (Example - To be refined in task 2.3) --- 
    
    def _serialize_profile(self, profile: AnalysisProfile) -> tuple:
        """Convert AnalysisProfile object to database row tuple."""
        return (
            str(profile.id),
            profile.name,
            profile.instructions,
            json.dumps(profile.schema_definition), # Store schema as JSON string
            profile.created_at.isoformat(),
            profile.updated_at.isoformat()
        )

    def _deserialize_profile(self, row: sqlite3.Row) -> AnalysisProfile:
        """Convert database row (sqlite3.Row) to AnalysisProfile object."""
        return AnalysisProfile(
            id=row['id'],
            name=row['name'],
            instructions=row['instructions'],
            schema_definition=json.loads(row['schema_definition']), # Load schema from JSON string
            created_at=datetime.fromisoformat(row['created_at']),
            updated_at=datetime.fromisoformat(row['updated_at'])
        )

    def close(self) -> None:
        """Close the database connection."""
        if self.conn:
            try:
                self.conn.close()
                self.conn = None
                logger.info("Database connection closed.")
            except sqlite3.Error as e:
                logger.error(f"Failed to close database connection: {e}")

    def __del__(self):
        """Ensure connection is closed when the object is destroyed."""
        self.close() 