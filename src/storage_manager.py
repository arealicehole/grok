# src/storage_manager.py
import sqlite3
import logging
import os
import json
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime

# Assuming AnalysisProfile model is defined in models.py
from .models.analysis_profile import AnalysisProfile

# Placeholder until models.py is created or updated
# class AnalysisProfile:
#     # Minimal placeholder for type hinting
#     def __init__(self, id: str, name: str, instructions: str, schema_definition: dict, created_at: datetime, updated_at: datetime):
#         self.id = id
#         self.name = name
#         self.instructions = instructions
#         self.schema_definition = schema_definition
#         self.created_at = created_at
#         self.updated_at = updated_at
# 
#     def to_dict(self) -> Dict[str, Any]:
#         return {
#             'id': str(self.id),
#             'name': self.name,
#             'instructions': self.instructions,
#             'schema_definition': self.schema_definition,
#             'created_at': self.created_at.isoformat(),
#             'updated_at': self.updated_at.isoformat()
#         }
# 
#     @classmethod
#     def from_dict(cls, data: Dict[str, Any]) -> 'AnalysisProfile':
#         # Basic reconstruction for now
#         return cls(
#             id=data['id'],
#             name=data['name'],
#             instructions=data.get('instructions', ''),
#             schema_definition=data.get('schema_definition', {}),
#             created_at=datetime.fromisoformat(data['created_at']) if data.get('created_at') else datetime.utcnow(),
#             updated_at=datetime.fromisoformat(data['updated_at']) if data.get('updated_at') else datetime.utcnow()
#         )

class StorageManager:
    """Manages different storage backends for Analysis Profiles."""

    def __init__(self, storage_type='sqlite', db_path=None):
        self.logger = logging.getLogger(__name__)
        self._storage = self._initialize_storage(storage_type, db_path)

    def _initialize_storage(self, storage_type, db_path):
        if storage_type == 'sqlite':
            # Initialize SQLite storage
            # (Assuming ProfileRepository is the SQLite implementation)
            try:
                # Dynamically import if needed, or assume it's globally available
                from .profile_repository import ProfileRepository
                return ProfileRepository(db_path=db_path)
            except ImportError:
                self.logger.error("Failed to import ProfileRepository for SQLite storage.")
                raise
            except Exception as e:
                self.logger.error(f"Failed to initialize SQLite storage: {e}")
                raise # Re-raise other initialization errors
        # Add other storage types here (e.g., 'json', 'memory')
        # elif storage_type == 'json':
        #     # Initialize JSON storage
        #     return JsonProfileStorage(...) 
        else:
            self.logger.error(f"Unsupported storage type: {storage_type}")
            raise ValueError(f"Unsupported storage type: {storage_type}")

    def save_profile(self, profile: AnalysisProfile) -> bool:
        """Saves a profile using the configured storage backend."""
        try:
            # The specific save methods might return different things
            # Adapt this based on the actual storage interface
            self.logger.info(f"Attempting to save profile: {profile.id} ({profile.name}) via StorageManager")
            result = self._storage.save_profile(profile)
            # Assuming save_profile returns the saved profile or raises on error
            if result:
                self.logger.info(f"Profile {profile.id} saved successfully.")
                return True
            else:
                # This case might depend on the repository implementation
                # If save_profile returns None or False on failure without raising
                self.logger.warning(f"Profile {profile.id} save operation returned a non-True value.")
                return False
        except Exception as e:
            # Catch specific exceptions from storage layer if defined (e.g., ProfileStorageError)
            self.logger.error(f"StorageManager: Error saving profile {profile.id}: {e}", exc_info=True)
            return False

    def load_profile(self, identifier: str) -> Optional[AnalysisProfile]:
        """Loads a profile by ID or name."""
        try:
            return self._storage.load_profile(identifier)
        except Exception as e:
            self.logger.error(f"StorageManager: Error loading profile '{identifier}': {e}", exc_info=True)
            return None

    def get_all_profiles(self, **kwargs) -> List[AnalysisProfile]:
        """Retrieves all profiles, passing through kwargs for filtering/pagination."""
        try:
            return self._storage.get_all_profiles(**kwargs)
        except Exception as e:
            self.logger.error(f"StorageManager: Error getting all profiles: {e}", exc_info=True)
            return []

    def delete_profile(self, profile_id: str) -> bool:
        """Deletes a profile by ID."""
        try:
            return self._storage.delete_profile(profile_id)
        except Exception as e:
            self.logger.error(f"StorageManager: Error deleting profile {profile_id}: {e}", exc_info=True)
            return False

    def profile_exists(self, identifier: str) -> bool:
        """Checks if a profile exists by ID or name."""
        try:
            return self._storage.profile_exists(identifier)
        except Exception as e:
            self.logger.error(f"StorageManager: Error checking profile existence for '{identifier}': {e}", exc_info=True)
            return False

    def perform_health_check(self) -> Dict[str, Any]:
        """Performs a health check on the configured storage backend."""
        try:
            # Check if the storage implementation has a health check method
            if hasattr(self._storage, 'perform_storage_health_check'):
                return self._storage.perform_storage_health_check()
            else:
                self.logger.warning(f"Storage backend type {type(self._storage).__name__} does not support health checks.")
                return {"status": "unknown", "message": "Health check not supported for this storage type."}
        except Exception as e:
            self.logger.error(f"StorageManager: Error performing health check: {e}", exc_info=True)
            return {"status": "error", "message": f"Health check failed: {e}"}

# Example Usage (optional)
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    
    # Create a dummy profile for testing
    dummy_profile = AnalysisProfile(
        id=str(uuid.uuid4()), 
        name="Test Profile via Manager", 
        instructions="Test instructions", 
        schema_definition={}, 
        created_at=datetime.utcnow(), 
        updated_at=datetime.utcnow()
    )
    
    try:
        storage_mgr = StorageManager(storage_type='sqlite')
        print("StorageManager initialized with SQLite.")
        
        # Test save
        # save_success = storage_mgr.save_profile(dummy_profile)
        # print(f"Save successful: {save_success}")

        # Test load (assuming profile exists)
        # loaded = storage_mgr.load_profile(dummy_profile.id)
        # if loaded:
        #     print(f"Loaded profile: {loaded.name}")
        # else:
        #     print("Failed to load profile.")
            
        # Test list
        all_profiles = storage_mgr.get_all_profiles()
        print(f"Found {len(all_profiles)} profiles.")

        # Test health check
        health = storage_mgr.perform_health_check()
        print(f"Health Check: {health}")

    except Exception as e:
        print(f"An error occurred: {e}") 