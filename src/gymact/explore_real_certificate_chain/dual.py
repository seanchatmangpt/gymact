from dataclasses import dataclass
from fractions import Fraction


@dataclass(frozen=True)
class DualResult:
    subject: str
    value: Fraction
    potential_digest: str


def bind_dual(subject: str, value: Fraction, potential_digest: str) -> DualResult:
    if not potential_digest:
        raise ValueError("DUAL_DIVERGENCE")
    return DualResult(subject, value, potential_digest)
