"""Bounded provider routing; never authority."""
from dataclasses import dataclass, field
from .envelope import Envelope
@dataclass(slots=True)
class ProviderRegistry:
    providers: tuple[str,...]
    excluded: set[str]=field(default_factory=set)
    def select(self,e:Envelope)->Envelope:
        c=e.candidate
        if c.provider in self.providers and c.provider not in self.excluded:return e
        for p in self.providers:
            if p not in self.excluded:return Envelope(type(c)(c.subject,c.effect_id,c.generation,p,c.replay_key),e.attempt,e.max_attempts,e.outcome)
        raise LookupError("provider_exhausted")
    def exclude(self,p:str)->None:self.excluded.add(p)
