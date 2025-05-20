import uuid
from datetime import datetime, timezone
from typing import Dict, Any, Optional
import json

class AnalysisProfile:
    """Represents an Analysis Profile for processing transcripts."""

    def __init__(
        self,
        name: str,
        instructions: str = "",
        schema_definition: Optional[Dict[str, Any]] = None,
        id: Optional[uuid.UUID] = None,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
        version: str = "1.0"
    ):
        self.id: uuid.UUID = id or uuid.uuid4()
        self.name: str = name
        self.instructions: str = instructions
        self.schema_definition: Dict[str, Any] = schema_definition or {}
        now = datetime.now(timezone.utc)
        self.created_at: datetime = created_at or now
        self.updated_at: datetime = updated_at or self.created_at
        self.version: str = version

        if not self.is_valid():
            # More specific errors could be raised based on which validation failed
            raise ValueError("Invalid AnalysisProfile parameters provided during initialization.")

    def is_valid(self) -> bool:
        """Performs basic validation on the profile attributes."""
        if not self.name or not isinstance(self.name, str):
            print(f"Validation failed: Invalid name '{self.name}'")
            return False

        if not isinstance(self.instructions, str):
            print("Validation failed: Instructions must be a string.")
            return False

        if not isinstance(self.schema_definition, dict):
            print("Validation failed: Schema definition must be a dictionary.")
            return False
            
        # Basic structural check for schema (as per PRD context)
        if self.schema_definition:
             # Check if schema_definition is a dict - already checked above
             # Further validation could check for specific keys like 'input', 'output' if required
             # For now, just ensuring it's a dict is sufficient based on initial requirements
             pass
             
        if not isinstance(self.created_at, datetime):
             print("Validation failed: created_at must be a datetime object.")
             return False
             
        if not isinstance(self.updated_at, datetime):
             print("Validation failed: updated_at must be a datetime object.")
             return False
             
        if not isinstance(self.version, str) or not self.version:
             print("Validation failed: version must be a non-empty string.")
             return False

        return True

    def update(self, **kwargs) -> None:
        """Updates profile attributes and sets the updated_at timestamp."""
        for key, value in kwargs.items():
            # Ensure we only update existing attributes
            if hasattr(self, key) and key not in ['id', 'created_at']:
                setattr(self, key, value)
        self.updated_at = datetime.now(timezone.utc)
        
        # Re-validate after update
        if not self.is_valid():
             # Decide on handling: revert changes or raise error?
             # Raising an error is safer to prevent invalid states.
             raise ValueError("Update resulted in an invalid AnalysisProfile state.")


    def to_dict(self) -> Dict[str, Any]:
        """Converts the profile object to a dictionary for serialization."""
        return {
            'id': str(self.id),
            'name': self.name,
            'instructions': self.instructions,
            'schema_definition': self.schema_definition, # Stored directly as dict
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'version': self.version,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AnalysisProfile':
        """Creates an AnalysisProfile instance from a dictionary."""
        # Basic check for required fields in the dictionary
        if 'name' not in data or 'id' not in data:
             raise ValueError("Dictionary must contain at least 'id' and 'name' keys.")
             
        # Convert ISO format strings back to datetime objects
        created_at_obj = None
        if 'created_at' in data and isinstance(data['created_at'], str):
            try:
                created_at_obj = datetime.fromisoformat(data['created_at'])
                # Ensure timezone-awareness (assuming UTC if not specified)
                if created_at_obj.tzinfo is None:
                    created_at_obj = created_at_obj.replace(tzinfo=timezone.utc)
            except ValueError:
                 raise ValueError("Invalid ISO format for created_at")
        elif isinstance(data.get('created_at'), datetime):
             created_at_obj = data['created_at']


        updated_at_obj = None
        if 'updated_at' in data and isinstance(data['updated_at'], str):
            try:
                updated_at_obj = datetime.fromisoformat(data['updated_at'])
                 # Ensure timezone-awareness (assuming UTC if not specified)
                if updated_at_obj.tzinfo is None:
                    updated_at_obj = updated_at_obj.replace(tzinfo=timezone.utc)
            except ValueError:
                 raise ValueError("Invalid ISO format for updated_at")
        elif isinstance(data.get('updated_at'), datetime):
             updated_at_obj = data['updated_at']


        # Convert id string back to UUID object
        id_obj = None
        if 'id' in data and isinstance(data['id'], str):
             try:
                 id_obj = uuid.UUID(data['id'])
             except ValueError:
                 # Raise a more specific error if the string is not a valid UUID
                 raise ValueError(f"Invalid UUID format for id: '{data['id']}'")
        elif isinstance(data.get('id'), uuid.UUID):
            id_obj = data['id']

        # If after processing, id_obj is still None, it means the input ID was problematic
        # or missing (though initial check should catch missing)
        if id_obj is None:
            raise ValueError("Failed to determine a valid UUID for the profile ID.")


        return cls(
            id=id_obj,
            name=data['name'],
            instructions=data.get('instructions', ""),
            schema_definition=data.get('schema_definition', {}),
            created_at=created_at_obj,
            updated_at=updated_at_obj,
            version=data.get('version', "1.0")
        )

    def __repr__(self) -> str:
        return (f"AnalysisProfile(id={self.id!r}, name={self.name!r}, "
                f"version={self.version!r}, updated_at={self.updated_at!r})")

    def __str__(self) -> str:
        return f"Analysis Profile '{self.name}' (ID: {self.id}, Version: {self.version})"

# Example Usage (optional, for testing)
if __name__ == '__main__':
    # Example schema
    sample_schema = {
        "type": "object",
        "properties": {
            "summary": {"type": "string"},
            "action_items": {"type": "array", "items": {"type": "string"}}
        },
        "required": ["summary"]
    }

    # Create a profile
    try:
        profile1 = AnalysisProfile(
            name="Meeting Summary",
            instructions="Extract the main summary and action items from the meeting transcript.",
            schema_definition=sample_schema
        )
        print(f"Created: {profile1}")
        print(f"Repr: {profile1!r}")

        # Convert to dict
        profile_dict = profile1.to_dict()
        print("\nDictionary representation:")
        print(json.dumps(profile_dict, indent=2))

        # Create from dict
        profile2 = AnalysisProfile.from_dict(profile_dict)
        print(f"\nRecreated from dict: {profile2}")
        print(f"Objects are equal: {profile1.id == profile2.id and profile1.name == profile2.name}") # Basic check

        # Update profile
        profile2.update(instructions="Updated instructions.", name="Meeting Summary v2")
        print(f"\nUpdated profile: {profile2}")
        print(f"Updated at: {profile2.updated_at}")
        
        # Test validation failure (e.g., empty name)
        invalid_data = profile_dict.copy()
        invalid_data['name'] = ""
        try:
            AnalysisProfile.from_dict(invalid_data)
        except ValueError as e:
            print(f"\nCaught expected validation error: {e}")

    except ValueError as e:
        print(f"\nError creating/using profile: {e}") 