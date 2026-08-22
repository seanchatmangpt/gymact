from __future__ import annotations

from .candidates import Candidate


def discover(
    candidates: tuple[Candidate, ...], required: frozenset[str]
) -> tuple[Candidate, ...]:
    viable = (candidate for candidate in candidates if required <= candidate.capabilities)
    return tuple(sorted(viable, key=lambda candidate: candidate.name))
