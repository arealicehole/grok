from datetime import datetime
from typing import Dict, Any

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