import datetime
from typing import Dict, Any, Optional

class AnalysisProfile:
    """Represents an analysis profile configuration."""
    def __init__(self,
                 name: str,
                 instructions: str,
                 schema_definition: str,
                 id: Optional[int] = None,
                 order: Optional[int] = None,
                 created_at: Optional[str] = None,
                 updated_at: Optional[str] = None,
                 last_used_timestamp: Optional[str] = None,
                 usage_count: int = 0):
        """Initializes an AnalysisProfile instance."""
        self.id: Optional[int] = id
        self.name: str = name
        self.instructions: str = instructions
        self.schema_definition: str = schema_definition
        self.order: Optional[int] = order
        self.created_at: str = created_at or datetime.datetime.now().isoformat()
        self.updated_at: str = updated_at or datetime.datetime.now().isoformat()
        self.last_used_timestamp: Optional[str] = last_used_timestamp
        self.usage_count: int = usage_count

    def to_dict(self) -> Dict[str, Any]:
        """Converts the profile to a dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "instructions": self.instructions,
            "schema_definition": self.schema_definition,
            "order": self.order,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "last_used_timestamp": self.last_used_timestamp,
            "usage_count": self.usage_count
        }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> 'AnalysisProfile':
        """Creates an AnalysisProfile from a dictionary."""
        return AnalysisProfile(
            id=data.get("id"),
            name=data.get("name", ""),
            instructions=data.get("instructions", ""),
            schema_definition=data.get("schema_definition", ""),
            order=data.get("order"),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
            last_used_timestamp=data.get("last_used_timestamp"),
            usage_count=data.get("usage_count", 0)
        )

    def __repr__(self) -> str:
        """Returns a string representation of the profile."""
        return (f"AnalysisProfile(id={self.id}, name='{self.name}', order={self.order}, "
                f"created_at='{self.created_at}', updated_at='{self.updated_at}', "
                f"last_used_timestamp='{self.last_used_timestamp}', usage_count={self.usage_count})") 