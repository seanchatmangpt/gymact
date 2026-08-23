from __future__ import annotations

from dataclasses import dataclass

from .calibration import DecisionCalibration
from .decision import DecisionResult
from .dependence import DependenceEvidence
from .errors import Refused
from .receipt import Receipt
from .standing import Standing


@dataclass(frozen=True)
class Qualification:
    standing: Standing
    receipt: Receipt | None


def qualify(
    *,
    subject_key: str,
    strategy: str,
    decision: DecisionResult,
    calibration: DecisionCalibration,
    dependence: DependenceEvidence,
    methodologies_closed: bool,
    dependency_broken: bool,
    exact_subject_executed: bool,
) -> Qualification:
    if dependency_broken:
        return Qualification(Standing.BUILD_BROKEN, None)
    if not exact_subject_executed:
        return Qualification(Standing.UNKNOWN, None)
    if not methodologies_closed:
        raise Refused("INCOMPLETE_METHODOLOGY")
    if decision.decision.value == "INDEPENDENT" and not dependence.independence_admissible:
        raise Refused("UNPROVEN_INDEPENDENCE")
    standing = Standing.PARTIAL_ALIVE
    receipt = Receipt(
        subject=subject_key,
        strategy=strategy,
        decision=decision.decision.value,
        standing=standing,
        evidence_generation=calibration.generation,
    )
    return Qualification(standing, receipt)
