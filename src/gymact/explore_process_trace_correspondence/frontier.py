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
    no_worse = a.exact >= b.exact and a.partial_order >= b.partial_order and a.conformance >= b.conformance and a.cost <= b.cost
    strict = a.exact > b.exact or a.partial_order > b.partial_order or a.conformance > b.conformance or a.cost < b.cost
    return no_worse and strict


def pareto(candidates: tuple[Candidate, ...]) -> tuple[Candidate, ...]:
    return tuple(sorted((c for c in candidates if not any(dominates(o, c) for o in candidates if o != c)), key=lambda c: c.identity))
