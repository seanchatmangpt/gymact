from __future__ import annotations

from .information import acquisition_value
from .pareto import Candidate, frontier


def select_strongest(candidates: tuple[Candidate, ...]) -> tuple[Candidate, ...]:
    if not candidates:
        return ()
    strength = max(candidate.semantic_strength for candidate in candidates)
    return tuple(candidate for candidate in candidates if candidate.semantic_strength == strength)


def select_minimax_uncertainty(candidates: tuple[Candidate, ...]) -> tuple[Candidate, ...]:
    if not candidates:
        return ()
    width = min(candidate.uncertainty for candidate in candidates)
    return tuple(candidate for candidate in candidates if candidate.uncertainty == width)


def select_pareto(candidates: tuple[Candidate, ...]) -> tuple[Candidate, ...]:
    return frontier(candidates)


def select_information(candidates: tuple[Candidate, ...]) -> tuple[Candidate, ...]:
    if not candidates:
        return ()
    scored = {
        candidate: acquisition_value(
            __import__(
                "gymact.explore_evidence_composition.interval", fromlist=["Interval"]
            ).Interval(
                candidate.lower_confidence,
                min(1.0, candidate.lower_confidence + candidate.uncertainty),
            ),
            cost=candidate.cost,
            blocker_relief=candidate.semantic_strength,
        )
        for candidate in candidates
    }
    best = max(scored.values())
    return tuple(candidate for candidate in candidates if scored[candidate] == best)
