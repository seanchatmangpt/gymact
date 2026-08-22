from __future__ import annotations

import math
from dataclasses import dataclass
from fractions import Fraction

from .contracts import Refusal
from .trials import CalibrationTrial


@dataclass(frozen=True)
class CalibrationEstimate:
    source_id: str
    support: int
    true_positive_rate: Fraction
    false_positive_rate: Fraction
    brier_error: Fraction
    precision_lower_ppm: int

    @property
    def calibrated(self) -> bool:
        return self.support >= 4


def estimate(
    source_id: str,
    trials: tuple[CalibrationTrial, ...],
    *,
    delta_ppm: int = 50_000,
) -> CalibrationEstimate:
    own = [trial for trial in trials if trial.source_id == source_id]
    if not own:
        raise Refusal("REFUSED_NO_CALIBRATION_SUPPORT")
    if not 0 < delta_ppm < 1_000_000:
        raise Refusal("REFUSED_INVALID_CALIBRATION_DELTA")
    positives = sum(trial.actual_pass for trial in own)
    negatives = len(own) - positives
    true_positives = sum(trial.predicted_pass and trial.actual_pass for trial in own)
    false_positives = sum(
        trial.predicted_pass and not trial.actual_pass for trial in own
    )
    errors = sum(trial.predicted_pass != trial.actual_pass for trial in own)
    true_positive_rate = Fraction(true_positives + 1, positives + 2)
    false_positive_rate = Fraction(false_positives + 1, negatives + 2)
    brier_error = Fraction(errors, len(own))
    predicted_positive = sum(trial.predicted_pass for trial in own)
    empirical_precision = (
        Fraction(true_positives, predicted_positive)
        if predicted_positive
        else Fraction(0, 1)
    )
    radius = math.sqrt(
        math.log(1_000_000 / delta_ppm) / (2 * max(1, predicted_positive))
    )
    lower = max(0.0, float(empirical_precision) - radius)
    return CalibrationEstimate(
        source_id=source_id,
        support=len(own),
        true_positive_rate=true_positive_rate,
        false_positive_rate=false_positive_rate,
        brier_error=brier_error,
        precision_lower_ppm=int(lower * 1_000_000),
    )
