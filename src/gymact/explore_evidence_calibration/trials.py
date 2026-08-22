from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .contracts import Refusal


@dataclass(frozen=True)
class CalibrationTrial:
    source_id: str
    trial_id: str
    predicted_pass: bool
    actual_pass: bool
    observed_at: datetime

    def __post_init__(self) -> None:
        if not self.source_id or not self.trial_id:
            raise Refusal("REFUSED_INVALID_CALIBRATION_TRIAL")
        if self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise Refusal("REFUSED_NAIVE_CALIBRATION_TIME")


def admit_trials(
    trials: list[CalibrationTrial], *, now: datetime
) -> tuple[CalibrationTrial, ...]:
    if now.tzinfo is None or now.utcoffset() is None:
        raise Refusal("REFUSED_NAIVE_NOW")
    ids: set[tuple[str, str]] = set()
    admitted: list[CalibrationTrial] = []
    for trial in trials:
        key = (trial.source_id, trial.trial_id)
        if key in ids:
            raise Refusal("REFUSED_DUPLICATE_CALIBRATION_TRIAL")
        if trial.observed_at > now:
            raise Refusal("REFUSED_FUTURE_CALIBRATION_TRIAL")
        ids.add(key)
        admitted.append(trial)
    return tuple(sorted(admitted, key=lambda trial: (trial.source_id, trial.trial_id)))
