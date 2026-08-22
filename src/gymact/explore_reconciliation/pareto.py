from __future__ import annotations

from .candidate import Candidate


def pareto_frontier(candidates: tuple[Candidate, ...]) -> tuple[Candidate, ...]:
    result: list[Candidate] = []
    for candidate in candidates:
        dominated = any(
            other.candidate_id != candidate.candidate_id
            and other.cost <= candidate.cost
            and other.risk <= candidate.risk
            and (other.cost < candidate.cost or other.risk < candidate.risk)
            for other in candidates
        )
        if not dominated:
            result.append(candidate)
    return tuple(sorted(result, key=lambda item: item.candidate_id))
