from enum import StrEnum
from fractions import Fraction

from .calibration import GainCalibration

class FeedbackPolicy(StrEnum):
    HOLD = "HOLD"
    BIAS_CORRECT = "BIAS_CORRECT"
    DOWNSHIFT_UNDERPERFORMER = "DOWNSHIFT_UNDERPERFORMER"
    EXPLORE_DRIFT = "EXPLORE_DRIFT"
    MINIMAX_REGRET = "MINIMAX_REGRET"

def policy_score(policy: FeedbackPolicy, calibration: GainCalibration, drift: bool, regret: Fraction) -> Fraction:
    if policy is FeedbackPolicy.HOLD:
        return Fraction(0)
    if policy is FeedbackPolicy.BIAS_CORRECT:
        return -abs(calibration.mean_error)
    if policy is FeedbackPolicy.DOWNSHIFT_UNDERPERFORMER:
        return -calibration.mean_abs_error
    if policy is FeedbackPolicy.EXPLORE_DRIFT:
        return Fraction(1 if drift else 0)
    return -regret
