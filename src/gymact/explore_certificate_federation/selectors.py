from dataclasses import dataclass
from enum import StrEnum


class Selector(StrEnum):
    NEWEST = "NEWEST"
    MAX_RUNTIME_DIVERSITY = "MAX_RUNTIME_DIVERSITY"
    MAX_EFFECTIVE_EVIDENCE = "MAX_EFFECTIVE_EVIDENCE"
    MIN_COST = "MIN_COST"


@dataclass(frozen=True)
class Candidate:
    candidate_id: str
    generation: int
    runtime_diversity: int
    effective_evidence: float
    cost: int


def select(candidates: tuple[Candidate, ...], strategy: Selector) -> Candidate:
    if not candidates:
        raise ValueError("empty candidates")
    keys = {
        Selector.NEWEST: lambda c: (c.generation, c.candidate_id),
        Selector.MAX_RUNTIME_DIVERSITY: lambda c: (c.runtime_diversity, c.candidate_id),
        Selector.MAX_EFFECTIVE_EVIDENCE: lambda c: (c.effective_evidence, c.candidate_id),
        Selector.MIN_COST: lambda c: (-c.cost, c.candidate_id),
    }
    return max(candidates, key=keys[strategy])
