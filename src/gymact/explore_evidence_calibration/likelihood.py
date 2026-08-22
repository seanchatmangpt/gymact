from __future__ import annotations
from dataclasses import dataclass
import math
from .contracts import Refusal
from .estimate import CalibrationEstimate
from .witness import CurrentWitness

@dataclass(frozen=True)
class InformationContribution:
    evidence_id: str
    source_id: str
    milli_nats: int
    calibrated: bool

def contribution(witness: CurrentWitness, estimate: CalibrationEstimate | None) -> InformationContribution:
    if witness.outcome in {"PENDING", "UNKNOWN", "UNSUPPORTED"}:
        return InformationContribution(witness.evidence_id, witness.source_id, 0, bool(estimate and estimate.calibrated))
    if estimate is None or not estimate.calibrated:
        return InformationContribution(witness.evidence_id, witness.source_id, 0, False)
    tpr, fpr = float(estimate.true_positive_rate), float(estimate.false_positive_rate)
    if not 0 < tpr < 1 or not 0 < fpr < 1: raise Refusal("REFUSED_DEGENERATE_CALIBRATION")
    if witness.outcome == "PASS": value = math.log(tpr / fpr)
    elif witness.outcome == "FAIL": value = math.log((1-tpr)/(1-fpr))
    else: raise Refusal("REFUSED_INVALID_INFORMATION_OUTCOME")
    return InformationContribution(witness.evidence_id, witness.source_id, int(round(value*1000)), True)
