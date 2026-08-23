from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Candidate:
    identity: str
    exact: int
    partial_order: int
    conformance: float
    cost: int


def dominates(a: Candidate, b: Candidate) -> bool:
    no_worse = (
        a.exact >= b.exact
        and a.partial_order >= b.partial_order
        and a.conformance >= b.conformance
        and a.cost <= b.cost
    )
    strict = (
        a.exact > b.exact
        or a.partial_order > b.partial_order
        or a.conformance > b.conformance
        or a.cost < b.cost
    )
    return no_worse and strict


def pareto(candidates: tuple[Candidate, ...]) -> tuple[Candidate, ...]:
    survivors = (
        candidate
        for candidate in candidates
        if not any(dominates(other, candidate) for other in candidates if other != candidate)
    )
    return tuple(sorted(survivors, key=lambda candidate: candidate.identity))
