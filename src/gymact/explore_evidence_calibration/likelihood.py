from __future__ import annotations

import math
from dataclasses import dataclass

from .contracts import Refusal
from .estimate import CalibrationEstimate
from .witness import CurrentWitness


@dataclass(frozen=True)
class InformationContribution:
    evidence_id: str
    source_id: str
    milli_nats: int
    calibrated: bool


def contribution(
    witness: CurrentWitness, estimate: CalibrationEstimate | None
) -> InformationContribution:
    if witness.outcome in {"PENDING", "UNKNOWN", "UNSUPPORTED"}:
        calibrated = bool(estimate and estimate.calibrated)
        return InformationContribution(
            witness.evidence_id, witness.source_id, 0, calibrated
        )
    if estimate is None or not estimate.calibrated:
        return InformationContribution(witness.evidence_id, witness.source_id, 0, False)
    true_positive_rate = float(estimate.true_positive_rate)
    false_positive_rate = float(estimate.false_positive_rate)
    if not 0 < true_positive_rate < 1 or not 0 < false_positive_rate < 1:
        raise Refusal("REFUSED_DEGENERATE_CALIBRATION")
    if witness.outcome == "PASS":
        value = math.log(true_positive_rate / false_positive_rate)
    elif witness.outcome == "FAIL":
        value = math.log((1 - true_positive_rate) / (1 - false_positive_rate))
    else:
        raise Refusal("REFUSED_INVALID_INFORMATION_OUTCOME")
    return InformationContribution(
        witness.evidence_id, witness.source_id, round(value * 1000), True
    )
