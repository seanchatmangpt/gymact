from collections.abc import Iterable
from enum import StrEnum
from fractions import Fraction

from . import clipped, direct, doubly_robust, ips, snips
from .direct import ModelPrediction
from .logged import LoggedDecision
from .refusal import Refused


class OPEStrategy(StrEnum):
    IPS = "IPS"
    SNIPS = "SNIPS"
    CLIPPED_IPS = "CLIPPED_IPS"
    DIRECT_MODEL = "DIRECT_MODEL"
    DOUBLY_ROBUST = "DOUBLY_ROBUST"


def evaluate(
    strategy: OPEStrategy,
    decisions: Iterable[LoggedDecision],
    *,
    predictions: Iterable[ModelPrediction] = (),
    clip: Fraction = Fraction(3),
) -> Fraction:
    rows = tuple(decisions)
    prediction_rows = tuple(predictions)
    if strategy is OPEStrategy.IPS:
        return ips.estimate(rows)
    if strategy is OPEStrategy.SNIPS:
        return snips.estimate(rows)
    if strategy is OPEStrategy.CLIPPED_IPS:
        return clipped.estimate(rows, limit=clip)
    if not prediction_rows:
        raise Refused("REFUSED_MODEL_PREDICTIONS_REQUIRED", strategy.value)
    if strategy is OPEStrategy.DIRECT_MODEL:
        return direct.estimate(rows, prediction_rows)
    return doubly_robust.estimate(rows, prediction_rows)
