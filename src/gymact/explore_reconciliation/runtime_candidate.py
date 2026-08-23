from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RuntimeCandidate:
    name: str
    deterministic: bool
    network_required: bool
    live_external: bool

    def admitted_for_explore(self) -> bool:
        return self.deterministic and not self.live_external


def runtime_frontier(candidates: tuple[RuntimeCandidate, ...]) -> tuple[RuntimeCandidate, ...]:
    result = tuple(candidate for candidate in candidates if candidate.admitted_for_explore())
    if not result:
        raise ValueError("REFUSED_NO_REVERSIBLE_RUNTIME_CANDIDATE")
    return result
