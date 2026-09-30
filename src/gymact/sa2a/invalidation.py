"""Typed stale-plan invalidation without authority escalation."""
from dataclasses import dataclass
from .envelope import Envelope

@dataclass(frozen=True, slots=True)
class Invalidation:
    subject: str
    generation: int
    reason: str

class StaleCandidate(ValueError): pass

def admit_generation(e: Envelope, current_generation: int) -> Envelope:
    if e.candidate.generation != current_generation:
        raise StaleCandidate("stale_generation")
    return e

def invalidate(e: Envelope, reason: str = "superseded") -> Invalidation:
    return Invalidation(e.candidate.subject, e.candidate.generation, reason)
