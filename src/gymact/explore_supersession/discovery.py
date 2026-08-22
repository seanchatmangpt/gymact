from __future__ import annotations

from .candidates import Candidate


def discover(candidates: tuple[Candidate, ...], required: frozenset[str]) -> tuple[Candidate, ...]:
    return tuple(sorted((c for c in candidates if required <= c.capabilities), key=lambda c: c.name))
