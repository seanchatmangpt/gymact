from dataclasses import dataclass

from .strategies import AcquisitionStrategy


@dataclass(frozen=True, slots=True)
class StrategyVector:
    strategy: AcquisitionStrategy
    information: float
    coverage: float
    cost: int
    latency: int


def pareto_frontier(vectors: tuple[StrategyVector, ...]) -> tuple[StrategyVector, ...]:
    kept: list[StrategyVector] = []
    for candidate in vectors:
        dominated = False
        for other in vectors:
            if other is candidate:
                continue
            no_worse = (
                other.information >= candidate.information
                and other.coverage >= candidate.coverage
                and other.cost <= candidate.cost
                and other.latency <= candidate.latency
            )
            strict = (
                other.information > candidate.information
                or other.coverage > candidate.coverage
                or other.cost < candidate.cost
                or other.latency < candidate.latency
            )
            if no_worse and strict:
                dominated = True
                break
        if not dominated:
            kept.append(candidate)
    return tuple(sorted(kept, key=lambda item: item.strategy.value))
