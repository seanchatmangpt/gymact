from dataclasses import dataclass
from fractions import Fraction

from .capability import RailCapability
from .history import CalibrationTrial, TrialOutcome
from .subject import Refusal


@dataclass(frozen=True, slots=True)
class RailCalibration:
    rail: RailCapability
    support: int
    detection_rate: Fraction
    false_alarm_rate: Fraction

    @property
    def state(self) -> str:
        if self.support < 4:
            return "INSUFFICIENT"
        if self.detection_rate < Fraction(1, 2) or self.false_alarm_rate > Fraction(1, 4):
            return "UNRELIABLE"
        return "CALIBRATED"


def calibrate(rail: RailCapability, trials: tuple[CalibrationTrial, ...]) -> RailCalibration:
    selected = [trial for trial in trials if trial.rail.fingerprint == rail.fingerprint]
    if not selected:
        return RailCalibration(rail, 0, Fraction(0), Fraction(0))
    fault = [trial for trial in selected if trial.truth_fault]
    clean = [trial for trial in selected if not trial.truth_fault]
    detected = sum(trial.outcome is TrialOutcome.DETECTED for trial in fault)
    false_alarm = sum(trial.outcome is TrialOutcome.FALSE_ALARM for trial in clean)
    detection_rate = Fraction(detected, len(fault)) if fault else Fraction(0)
    false_alarm_rate = Fraction(false_alarm, len(clean)) if clean else Fraction(0)
    return RailCalibration(rail, len(selected), detection_rate, false_alarm_rate)


def require_current(calibration: RailCalibration, rail: RailCapability) -> None:
    if calibration.rail.fingerprint != rail.fingerprint:
        raise Refusal("REFUSED_STALE_RAIL_CALIBRATION")
