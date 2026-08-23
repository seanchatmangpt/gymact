from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SemanticCandidate:
    name: str
    media_type: str
    preserves_identity: bool
    deterministic: bool

    def admissible(self) -> bool:
        return self.preserves_identity and self.deterministic


def semantic_frontier(candidates: tuple[SemanticCandidate, ...]) -> tuple[SemanticCandidate, ...]:
    admitted = tuple(candidate for candidate in candidates if candidate.admissible())
    if not admitted:
        raise ValueError("REFUSED_NO_ADMISSIBLE_SEMANTIC_CANDIDATE")
    return admitted
