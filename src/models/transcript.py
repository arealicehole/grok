import datetime
from typing import Optional, Dict, Any, Union

class Transcript:
    '''Represents a text transcript to be analyzed.'''
    def __init__(
        self,
        text: str,
        id: Optional[int] = None,
        name: Optional[str] = None, # e.g., filename or title
        created_at: Optional[str] = None,
        updated_at: Optional[str] = None
    ):
        if not text:
            raise ValueError('Transcript: text cannot be empty.')

        self.id: Optional[int] = id
        self.name: Optional[str] = name
        self.text: str = text
        self.created_at: str = created_at or datetime.datetime.now().isoformat()
        self.updated_at: str = updated_at or datetime.datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        '''Converts the transcript to a dictionary.'''
        return {
            'id': self.id,
            'name': self.name,
            'text': self.text,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
        }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> 'Transcript':
        '''Creates a Transcript instance from a dictionary.'''
        return Transcript(
            id=data.get('id'),
            name=data.get('name'),
            text=data.get('text'),
            created_at=data.get('created_at'),
            updated_at=data.get('updated_at'),
        )

    def __repr__(self) -> str:
        '''Returns a string representation of the transcript.'''
        return (f"Transcript(id={self.id}, name='{self.name}', text_len={len(self.text)}, "
                f"created_at='{self.created_at}', updated_at='{self.updated_at}')") 