from __future__ import annotations

from .selector import Candidate

def dominates(a: Candidate, b: Candidate) -> bool:
    weak = (
        a.nominal <= b.nominal
        and a.worst <= b.worst
        and a.radius <= b.radius
        and a.support >= b.support
        and a.oracle_gap <= b.oracle_gap
    )
    strict = (
        a.nominal < b.nominal
        or a.worst < b.worst
        or a.radius < b.radius
        or a.support > b.support
        or a.oracle_gap < b.oracle_gap
    )
    return weak and strict

def frontier(candidates: tuple[Candidate, ...]) -> tuple[Candidate, ...]:
    return tuple(sorted((c for c in candidates if not any(dominates(o, c) for o in candidates if o != c)), key=lambda c: c.identity))
