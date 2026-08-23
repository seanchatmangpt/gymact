from __future__ import annotations

from .selectors import Score


def dominates(a: Score, b: Score) -> bool:
    no_worse = (
        a.fidelity_loss <= b.fidelity_loss
        and a.migration_cost <= b.migration_cost
        and a.runtime_cost <= b.runtime_cost
        and a.reversible >= b.reversible
    )
    strictly = (
        a.fidelity_loss < b.fidelity_loss
        or a.migration_cost < b.migration_cost
        or a.runtime_cost < b.runtime_cost
        or a.reversible > b.reversible
    )
    return no_worse and strictly


def frontier(scores: tuple[Score, ...]) -> tuple[Score, ...]:
    return tuple(
        s
        for s in sorted(scores, key=lambda x: x.candidate.fingerprint)
        if not any(dominates(other, s) for other in scores if other != s)
    )
