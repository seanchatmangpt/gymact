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
    for vector in vectors:
        dominated = any(
            candidate is not vector
            and candidate.calibration_error <= vector.calibration_error
            and candidate.regret <= vector.regret
            and candidate.exploration_cost <= vector.exploration_cost
            and (
                candidate.calibration_error,
                candidate.regret,
                candidate.exploration_cost,
            )
            != (vector.calibration_error, vector.regret, vector.exploration_cost)
            for candidate in vectors
        )
        if not dominated:
            out.append(vector)
    return sorted(out, key=lambda item: item.name)
