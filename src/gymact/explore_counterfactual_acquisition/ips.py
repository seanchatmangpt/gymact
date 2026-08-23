from collections.abc import Iterable
from fractions import Fraction

from .logged import LoggedDecision
from .refusal import Refused
from .weights import importance_weight


def estimate(decisions: Iterable[LoggedDecision]) -> Fraction:
    rows = tuple(decisions)
    if not rows:
        raise Refused("REFUSED_EMPTY_LOG")
    total = sum(
        (importance_weight(row) * row.realized_gain for row in rows),
        Fraction(),
    )
    return total / len(rows)
