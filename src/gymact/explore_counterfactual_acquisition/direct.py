from dataclasses import dataclass
from fractions import Fraction
import re
from typing import Iterable

from .logged import LoggedDecision
from .refusal import Refused

_SHA64 = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True, slots=True)
class ModelPrediction:
    decision_id: str
    target_gain: Fraction
    model_digest: str

    def __post_init__(self) -> None:
        if not self.decision_id or self.target_gain < 0:
            raise Refused("REFUSED_INVALID_MODEL_PREDICTION", self.decision_id)
        if not _SHA64.fullmatch(self.model_digest):
            raise Refused("REFUSED_INVALID_MODEL_DIGEST", self.model_digest)


def align(
    decisions: Iterable[LoggedDecision],
    predictions: Iterable[ModelPrediction],
) -> dict[str, ModelPrediction]:
    rows = tuple(decisions)
    prediction_rows = tuple(predictions)
    mapped = {prediction.decision_id: prediction for prediction in prediction_rows}
    if len(mapped) != len(prediction_rows):
        raise Refused("REFUSED_DUPLICATE_MODEL_PREDICTION")
    required = {row.decision_id for row in rows}
    if set(mapped) != required:
        raise Refused("REFUSED_INCOMPLETE_MODEL_PREDICTION")
    return mapped


def estimate(
    decisions: Iterable[LoggedDecision],
    predictions: Iterable[ModelPrediction],
) -> Fraction:
    rows = tuple(decisions)
    if not rows:
        raise Refused("REFUSED_EMPTY_LOG")
    mapped = align(rows, tuple(predictions))
    return sum((mapped[row.decision_id].target_gain for row in rows), Fraction()) / len(rows)
