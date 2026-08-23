from fractions import Fraction
from typing import Iterable

from .logged import LoggedDecision
from .refusal import Refused
from .weights import importance_weight


def estimate(decisions: Iterable[LoggedDecision]) -> Fraction:
    rows = tuple(decisions)
    if not rows:
        raise Refused("REFUSED_EMPTY_LOG")
    weights = tuple(importance_weight(row) for row in rows)
    denominator = sum(weights, Fraction())
    if denominator == 0:
        raise Refused("REFUSED_ZERO_TARGET_MASS")
    numerator = sum(
        (weight * row.realized_gain for weight, row in zip(weights, rows, strict=True)),
        Fraction(),
    )
    return numerator / denominator
