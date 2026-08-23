import math
from dataclasses import dataclass
from fractions import Fraction

from .calibration import RailCalibration


def binary_entropy(probability: Fraction) -> float:
    value = float(probability)
    if value <= 0.0 or value >= 1.0:
        return 0.0
    return -(value * math.log2(value) + (1 - value) * math.log2(1 - value))


@dataclass(frozen=True, slots=True)
class InformationEstimate:
    prior_fault: Fraction
    detect_probability: Fraction
    expected_entropy: float
    information_gain: float


def estimate_information(
    prior_fault: Fraction,
    calibration: RailCalibration,
) -> InformationEstimate:
    tpr = calibration.detection_rate
    fpr = calibration.false_alarm_rate
    detect_probability = prior_fault * tpr + (1 - prior_fault) * fpr
    no_detect_probability = 1 - detect_probability

    def posterior(detected: bool) -> Fraction:
        if detected:
            denominator = detect_probability
            numerator = prior_fault * tpr
        else:
            denominator = no_detect_probability
            numerator = prior_fault * (1 - tpr)
        return prior_fault if denominator == 0 else numerator / denominator

    expected = (
        float(detect_probability) * binary_entropy(posterior(True))
        + float(no_detect_probability) * binary_entropy(posterior(False))
    )
    gain = max(0.0, binary_entropy(prior_fault) - expected)
    return InformationEstimate(prior_fault, detect_probability, expected, gain)
