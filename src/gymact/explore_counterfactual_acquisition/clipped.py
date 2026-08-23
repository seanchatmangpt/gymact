from fractions import Fraction
from typing import Iterable

from .logged import LoggedDecision
from .refusal import Refused
from .weights import clipped_weight


def estimate(
    decisions: Iterable[LoggedDecision],
    *,
    limit: Fraction,
) -> Fraction:
    rows = tuple(decisions)
    if not rows:
        raise Refused("REFUSED_EMPTY_LOG")
    return sum(
        (clipped_weight(row, limit) * row.realized_gain for row in rows),
        Fraction(),
    ) / len(rows)
