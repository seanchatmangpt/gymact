import math
import random
from dataclasses import dataclass
from enum import StrEnum
from fractions import Fraction

from .calibration import RailCalibration
from .information import estimate_information


class AcquisitionStrategy(StrEnum):
    MAX_INFORMATION = "MAX_INFORMATION"
    INFORMATION_PER_COST = "INFORMATION_PER_COST"
    UCB_DISCOVERY = "UCB_DISCOVERY"
    THOMPSON_DISCOVERY = "THOMPSON_DISCOVERY"
    MINIMAX_COVERAGE = "MINIMAX_COVERAGE"


@dataclass(frozen=True, slots=True)
class Score:
    rail_fingerprint: str
    strategy: AcquisitionStrategy
    value: float


def score(
    calibration: RailCalibration,
    strategy: AcquisitionStrategy,
    prior_fault: Fraction,
    *,
    total_trials: int,
    seed: int = 0,
) -> Score:
    info = estimate_information(prior_fault, calibration)
    rail = calibration.rail
    if strategy is AcquisitionStrategy.MAX_INFORMATION:
        value = info.information_gain
    elif strategy is AcquisitionStrategy.INFORMATION_PER_COST:
        value = info.information_gain / rail.cost_millis
    elif strategy is AcquisitionStrategy.UCB_DISCOVERY:
        exploration = math.sqrt(2.0 * math.log(max(total_trials, 2)) / max(calibration.support, 1))
        value = float(calibration.detection_rate) + exploration
    elif strategy is AcquisitionStrategy.THOMPSON_DISCOVERY:
        rng = random.Random(f"{seed}:{rail.fingerprint}")
        detected = round(float(calibration.detection_rate) * calibration.support)
        value = rng.betavariate(1 + detected, 1 + max(calibration.support - detected, 0))
    else:
        value = min(
            float(calibration.detection_rate),
            1.0 - float(calibration.false_alarm_rate),
        )
    return Score(rail.fingerprint, strategy, value)
