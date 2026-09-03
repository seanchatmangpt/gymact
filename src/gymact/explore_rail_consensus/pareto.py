from dataclasses import dataclass

from .consensus import ConsensusStrategy


@dataclass(frozen=True, slots=True)
class StrategyVector:
    strategy: ConsensusStrategy
    safety: int
    evidence_cost: int
    liveness: int


def pareto_frontier(vectors: tuple[StrategyVector, ...]) -> tuple[StrategyVector, ...]:
    kept: list[StrategyVector] = []
    for candidate in vectors:
        dominated = False
        for other in vectors:
            if other is candidate:
                continue
            no_worse = (
                other.safety >= candidate.safety
                and other.liveness >= candidate.liveness
                and other.evidence_cost <= candidate.evidence_cost
            )
            strictly = (
                other.safety > candidate.safety
                or other.liveness > candidate.liveness
                or other.evidence_cost < candidate.evidence_cost
            )
            if no_worse and strictly:
                dominated = True
                break
        if not dominated:
            kept.append(candidate)
    return tuple(sorted(kept, key=lambda x: x.strategy.value))
