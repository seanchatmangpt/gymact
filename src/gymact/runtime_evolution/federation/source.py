"""federation.source: bounded runtime-evolution primitive."""
from dataclasses import dataclass, field
from typing import Any
@dataclass(frozen=True, slots=True)
class Source:
    subject: str
    epoch: int = 0
    facts: tuple[str,...] = field(default_factory=tuple)
    def admits(self)->bool: return bool(self.subject) and self.epoch >= 0
    def evolve(self,*facts:str)->"Source":
        delta=tuple(x for x in facts if x and x not in self.facts)
        return type(self)(self.subject,self.epoch+1,self.facts+delta)
    def receipt(self)->dict[str,Any]:
        return {"wave":"federation","kind":"source","subject":self.subject,"epoch":self.epoch,"facts":list(self.facts)}
