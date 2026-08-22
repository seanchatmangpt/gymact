from __future__ import annotations
from dataclasses import dataclass
from .strategies import FusionResult

@dataclass(frozen=True)
class StrategyVector:
    strategy: str
    safety: int
    information: int
    reuse: int

def vector(result: FusionResult) -> StrategyVector:
    return StrategyVector(result.strategy.value, 100-20*len(result.under_calibrated)-100*bool(result.failures), abs(result.score), 100 if result.strategy.value=="UNIFORM_CLUSTER" else 70)

def pareto(vectors: tuple[StrategyVector, ...]) -> tuple[StrategyVector, ...]:
    survivors=[]
    for candidate in vectors:
        dominated=any(other is not candidate and other.safety>=candidate.safety and other.information>=candidate.information and other.reuse>=candidate.reuse and (other.safety,other.information,other.reuse)!=(candidate.safety,candidate.information,candidate.reuse) for other in vectors)
        if not dominated: survivors.append(candidate)
    return tuple(sorted(survivors,key=lambda item:item.strategy))
