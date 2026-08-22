from __future__ import annotations
from dataclasses import dataclass
from .strategies import FreshnessDecision

@dataclass(frozen=True, slots=True)
class StrategyResult:
    name: str
    safety: int
    reuse: int
    requalification_cost: int
    standing: str

def score(decision: FreshnessDecision) -> StrategyResult:
    safety={"PARTIAL_ALIVE":3,"REQUALIFYING":2,"UNKNOWN":1}.get(decision.standing,0)
    reuse=1 if decision.reusable else 0
    cost=0 if decision.reusable else (1 if decision.standing=="REQUALIFYING" else 2)
    return StrategyResult(decision.strategy.value,safety,reuse,cost,decision.standing)

def pareto(results: tuple[StrategyResult,...]) -> tuple[StrategyResult,...]:
    kept=[]
    for r in results:
        dominated=any((o.safety>=r.safety and o.reuse>=r.reuse and o.requalification_cost<=r.requalification_cost)
                      and (o.safety>r.safety or o.reuse>r.reuse or o.requalification_cost<r.requalification_cost)
                      for o in results if o is not r)
        if not dominated: kept.append(r)
    return tuple(sorted(kept,key=lambda x:x.name))
