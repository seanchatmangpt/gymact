from __future__ import annotations
from dataclasses import dataclass
from fractions import Fraction
import math
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

def estimate(source_id: str, trials: tuple[CalibrationTrial, ...], *, delta_ppm: int = 50_000) -> CalibrationEstimate:
    own = [t for t in trials if t.source_id == source_id]
    if not own:
        raise Refusal("REFUSED_NO_CALIBRATION_SUPPORT")
    if not 0 < delta_ppm < 1_000_000:
        raise Refusal("REFUSED_INVALID_CALIBRATION_DELTA")
    positives = sum(t.actual_pass for t in own); negatives = len(own) - positives
    tp = sum(t.predicted_pass and t.actual_pass for t in own); fp = sum(t.predicted_pass and not t.actual_pass for t in own)
    errors = sum(t.predicted_pass != t.actual_pass for t in own)
    tpr = Fraction(tp + 1, positives + 2); fpr = Fraction(fp + 1, negatives + 2)
    predicted_positive = sum(t.predicted_pass for t in own)
    precision = Fraction(tp, predicted_positive) if predicted_positive else Fraction(0, 1)
    radius = math.sqrt(math.log(1_000_000 / delta_ppm) / (2 * max(1, predicted_positive)))
    return CalibrationEstimate(source_id, len(own), tpr, fpr, Fraction(errors, len(own)), int(max(0.0, float(precision)-radius)*1_000_000))
