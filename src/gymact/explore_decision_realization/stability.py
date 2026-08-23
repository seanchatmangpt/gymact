from collections.abc import Iterable

from .decision import Decision
from .errors import Refused


def churn_rate(decisions: Iterable[Decision]) -> float:
    rows = tuple(decisions)
    if len(rows) < 2:
        raise Refused("INSUFFICIENT_REALIZATION_SUPPORT")
    changes = sum(left is not right for left, right in zip(rows, rows[1:], strict=False))
    return changes / (len(rows) - 1)


def transition_counts(decisions: Iterable[Decision]) -> dict[tuple[Decision, Decision], int]:
    rows = tuple(decisions)
    if len(rows) < 2:
        raise Refused("INSUFFICIENT_REALIZATION_SUPPORT")
    counts: dict[tuple[Decision, Decision], int] = {}
    for edge in zip(rows, rows[1:], strict=False):
        counts[edge] = counts.get(edge, 0) + 1
    return counts
