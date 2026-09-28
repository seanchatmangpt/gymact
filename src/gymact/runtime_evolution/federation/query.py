"""federation.query: bounded runtime-evolution primitive."""
from dataclasses import dataclass, field
from typing import Any
@dataclass(frozen=True, slots=True)
class Query:
    subject: str
    epoch: int = 0
    facts: tuple[str,...] = field(default_factory=tuple)
    def admits(self)->bool: return bool(self.subject) and self.epoch >= 0
    def evolve(self,*facts:str)->"Query":
        delta=tuple(x for x in facts if x and x not in self.facts)
        return type(self)(self.subject,self.epoch+1,self.facts+delta)
    def receipt(self)->dict[str,Any]:
        return {"wave":"federation","kind":"query","subject":self.subject,"epoch":self.epoch,"facts":list(self.facts)}
