from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any

# Forward declaration if AnalysisProfile is in another file
# class AnalysisProfile:
#     pass
# Or import it if defined
# from .models import AnalysisProfile 

class StorageInterface(ABC):
    """Abstract base class for Analysis Profile storage."""

    @abstractmethod
    def initialize(self) -> None:
        """Initialize the storage backend (e.g., create tables)."""
        pass

    @abstractmethod
    def save_profile(self, profile: Any) -> bool:
        """Save or update an Analysis Profile.
        
        Args:
            profile: The AnalysisProfile object to save.
            
        Returns:
            bool: True if successful, False otherwise.
        """
        pass

    @abstractmethod
    def get_profile_by_id(self, profile_id: str) -> Optional[Any]:
        """Retrieve a profile by its unique ID.
        
        Args:
            profile_id: The UUID string of the profile.
            
        Returns:
            Optional[AnalysisProfile]: The found profile or None.
        """
        pass
        
    @abstractmethod
    def get_profile_by_name(self, name: str) -> Optional[Any]:
        """Retrieve a profile by its name.
        
        Args:
            name: The unique name of the profile.
            
        Returns:
            Optional[AnalysisProfile]: The found profile or None.
        """
        pass

    @abstractmethod
    def list_profiles(self, filters: Optional[Dict[str, Any]] = None) -> List[Any]:
        """List all profiles, potentially filtered.
        
        Args:
            filters: Optional dictionary of filter criteria.
            
        Returns:
            List[AnalysisProfile]: A list of profiles matching the criteria.
        """
        pass

    @abstractmethod
    def delete_profile(self, profile_id: str) -> bool:
        """Delete a profile by its ID.
        
        Args:
            profile_id: The UUID string of the profile to delete.
            
        Returns:
            bool: True if deletion was successful, False otherwise.
        """
        pass

    @abstractmethod
    def close(self) -> None:
        """Close the storage connection if applicable."""
        pass 