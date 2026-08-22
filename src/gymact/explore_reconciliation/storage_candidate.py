from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class StorageCandidate:
    name: str
    durable: bool
    deterministic: bool
    external_side_effects: bool = False

    def admitted_for_explore(self) -> bool:
        return self.deterministic and not self.external_side_effects


def storage_frontier(candidates: tuple[StorageCandidate, ...]) -> tuple[StorageCandidate, ...]:
    frontier = tuple(candidate for candidate in candidates if candidate.admitted_for_explore())
    if not frontier:
        raise ValueError("REFUSED_NO_REVERSIBLE_STORAGE_CANDIDATE")
    return frontier
