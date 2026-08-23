from fractions import Fraction
from typing import Iterable

from .direct import ModelPrediction, align
from .logged import LoggedDecision
from .refusal import Refused
from .weights import importance_weight


def estimate(
    decisions: Iterable[LoggedDecision],
    predictions: Iterable[ModelPrediction],
) -> Fraction:
    rows = tuple(decisions)
    if not rows:
        raise Refused("REFUSED_EMPTY_LOG")
    mapped = align(rows, tuple(predictions))
    total = Fraction()
    for row in rows:
        prediction = mapped[row.decision_id].target_gain
        total += prediction + importance_weight(row) * (row.realized_gain - prediction)
    return total / len(rows)
