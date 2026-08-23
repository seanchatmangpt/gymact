from collections.abc import Iterable
from dataclasses import dataclass
from fractions import Fraction

from .logged import LoggedDecision
from .refusal import Refused
from .weights import importance_weight


@dataclass(frozen=True, slots=True)
class WeightDiagnostics:
    effective_sample_size: Fraction
    effective_sample_ratio: Fraction
    max_weight: Fraction
    mean_weight: Fraction


def diagnose(decisions: Iterable[LoggedDecision]) -> WeightDiagnostics:
    rows = tuple(decisions)
    if not rows:
        raise Refused("REFUSED_EMPTY_LOG")
    weights = tuple(importance_weight(row) for row in rows)
    total = sum(weights, Fraction())
    squares = sum((weight * weight for weight in weights), Fraction())
    if squares == 0:
        raise Refused("REFUSED_ZERO_TARGET_MASS")
    ess = total * total / squares
    return WeightDiagnostics(
        effective_sample_size=ess,
        effective_sample_ratio=ess / len(rows),
        max_weight=max(weights),
        mean_weight=total / len(rows),
    )
