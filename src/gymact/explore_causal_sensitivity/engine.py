from dataclasses import dataclass
from fractions import Fraction

from .e_value import evidence_value
from .evidence import LoggedOutcome
from .gamma import Gamma
from .manski import Interval
from .robust_ips import robust_ips


@dataclass(frozen=True)
class Evaluation:
    interval: Interval
    evidence_value: Fraction
    standing: str


def evaluate(
    rows: tuple[LoggedOutcome, ...],
    gamma: Fraction,
    outcome_span: Fraction,
) -> Evaluation:
    interval = robust_ips(rows, Gamma(gamma))
    value = evidence_value(interval, outcome_span)
    standing = "PARTIAL_ALIVE" if rows else "UNKNOWN"
    return Evaluation(interval, value, standing)
