from dataclasses import dataclass
from .subject import Subject
@dataclass(frozen=True, slots=True)
class Evidence:
    subject:Subject; receipt:str; schema:str; scope:str; standing:str
    def __post_init__(self):
        if len(self.receipt)!=64 or any(c not in '0123456789abcdef' for c in self.receipt): raise ValueError('REFUSED_INVALID_RECEIPT')
        if not self.schema: raise ValueError('REFUSED_EMPTY_SCHEMA')
