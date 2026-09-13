from __future__ import annotations

from dataclasses import dataclass

from .strategies import RolloverStrategy, StrategyResult, evaluate
from .witness import WitnessKind


@dataclass(frozen=True)
class Differential:
    results: tuple[StrategyResult, ...]

    @property
    def distinct_completion_count(self) -> int:
        return len({r.complete for r in self.results})


def compare(frontier: dict[str, WitnessKind], consumers: tuple[str, ...], critical: frozenset[str]) -> Differential:
    return Differential(tuple(evaluate(s, frontier, consumers, critical) for s in RolloverStrategy))
