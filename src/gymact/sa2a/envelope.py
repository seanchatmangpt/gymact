"""Portable powerless SA2A envelope."""
from dataclasses import dataclass
from .contract import Candidate
@dataclass(frozen=True, slots=True)
class Envelope:
    candidate: Candidate
    attempt: int = 0
    max_attempts: int = 3
    outcome: str = "candidate"
    @property
    def identity(self): return (self.candidate.subject,self.candidate.effect_id,self.candidate.generation,self.candidate.replay_key)
