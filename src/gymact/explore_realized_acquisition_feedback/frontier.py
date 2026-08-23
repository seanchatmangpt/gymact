from dataclasses import dataclass
from fractions import Fraction

@dataclass(frozen=True)
class PolicyVector:
    name: str
    calibration_error: Fraction
    regret: Fraction
    exploration_cost: Fraction

def pareto_frontier(vectors: list[PolicyVector]) -> list[PolicyVector]:
    out: list[PolicyVector] = []
    for v in vectors:
        dominated = any(
            u is not v
            and u.calibration_error <= v.calibration_error
            and u.regret <= v.regret
            and u.exploration_cost <= v.exploration_cost
            and (u.calibration_error, u.regret, u.exploration_cost) != (v.calibration_error, v.regret, v.exploration_cost)
            for u in vectors
        )
        if not dominated:
            out.append(v)
    return sorted(out, key=lambda x: x.name)
