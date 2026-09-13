from dataclasses import dataclass
from fractions import Fraction


@dataclass(frozen=True)
class PrimalResult:
    subject: str
    value: Fraction
    plan_digest: str


def bind_primal(subject: str, value: Fraction, plan_digest: str) -> PrimalResult:
    if value < 0 or not plan_digest:
        raise ValueError("SOLVER_DIVERGENCE")
    return PrimalResult(subject, value, plan_digest)
