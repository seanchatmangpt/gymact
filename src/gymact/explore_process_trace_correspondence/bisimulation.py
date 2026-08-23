from __future__ import annotations

from dataclasses import dataclass

from .divergence import Divergence, first_divergence
from .trace import Trace


@dataclass(frozen=True)
class BisimulationWitness:
    matched_steps: int
    complete: bool
    divergence: Divergence | None


def bounded_bisimulation(left: Trace, right: Trace, bound: int) -> BisimulationWitness:
    if bound < 0:
        raise ValueError("bound must be nonnegative")
    divergence = first_divergence(left, right)
    if divergence is None:
        matched = min(len(left.events), bound)
        return BisimulationWitness(matched, len(left.events) <= bound, None)
    matched = max(0, min(divergence.index, bound))
    return BisimulationWitness(matched, False, divergence)
