from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True, order=True)
class Candidate:
    name: str
    durable: bool
    transactional: bool
    external_authority: bool = False

def discover_candidates() -> tuple[Candidate, ...]:
    return (
        Candidate("memory", False, False),
        Candidate("jsonl", True, False),
        Candidate("sqlite", True, True),
    )

def lawful_candidates() -> tuple[Candidate, ...]:
    return tuple(c for c in discover_candidates() if not c.external_authority)
