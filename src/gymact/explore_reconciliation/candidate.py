from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Candidate:
    candidate_id: str
    capabilities: frozenset[str]
    reversible: bool
    cost: float
    risk: float

    def __post_init__(self) -> None:
        if not self.candidate_id.strip() or not self.capabilities:
            raise ValueError("REFUSED_INVALID_CANDIDATE")
        if not self.reversible:
            raise ValueError("REFUSED_IRREVERSIBLE_EXPLORE_CANDIDATE")
        if self.cost < 0 or not 0 <= self.risk <= 1:
            raise ValueError("REFUSED_INVALID_CANDIDATE_SCORE")


def discover(candidates: tuple[Candidate, ...], required: set[str]) -> tuple[Candidate, ...]:
    return tuple(c for c in candidates if required <= c.capabilities)
