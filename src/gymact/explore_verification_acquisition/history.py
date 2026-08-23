from dataclasses import dataclass
from enum import StrEnum

from .capability import RailCapability
from .subject import Refusal


class TrialOutcome(StrEnum):
    DETECTED = "DETECTED"
    MISSED = "MISSED"
    FALSE_ALARM = "FALSE_ALARM"
    CLEAN = "CLEAN"


@dataclass(frozen=True, slots=True)
class CalibrationTrial:
    rail: RailCapability
    scenario_id: str
    outcome: TrialOutcome
    truth_fault: bool

    def __post_init__(self) -> None:
        if not self.scenario_id:
            raise Refusal("REFUSED_INVALID_SCENARIO")
        if self.truth_fault and self.outcome not in {TrialOutcome.DETECTED, TrialOutcome.MISSED}:
            raise Refusal("REFUSED_TRIAL_TRUTH_MISMATCH")
        if not self.truth_fault and self.outcome not in {
            TrialOutcome.FALSE_ALARM,
            TrialOutcome.CLEAN,
        }:
            raise Refusal("REFUSED_TRIAL_TRUTH_MISMATCH")


def admit_trials(trials: tuple[CalibrationTrial, ...]) -> tuple[CalibrationTrial, ...]:
    seen: set[tuple[str, str]] = set()
    for trial in trials:
        key = (trial.rail.fingerprint, trial.scenario_id)
        if key in seen:
            raise Refusal("REFUSED_DUPLICATE_CALIBRATION_TRIAL")
        seen.add(key)
    return tuple(sorted(trials, key=lambda item: (item.rail.fingerprint, item.scenario_id)))
