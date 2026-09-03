from __future__ import annotations

from dataclasses import dataclass

from .admission import AdmissionPolicy, admit
from .calibration import CalibrationEvidence
from .frontier import current_frontier
from .meta_selector import SelectionBundle, compare
from .metamorphic import MetamorphicWitness
from .oracle import OracleWitness, require_independent
from .receipt import Receipt
from .standing import Standing, derive


@dataclass(frozen=True)
class Qualification:
    bundle: SelectionBundle | None
    standing: Standing
    receipt: Receipt | None


def qualify(
    evidence: tuple[CalibrationEvidence, ...],
    witnesses: dict[object, MetamorphicWitness],
    oracles: tuple[OracleWitness, ...],
    policy: AdmissionPolicy,
    *,
    hard_failure: bool = False,
) -> Qualification:
    frontier = current_frontier(evidence)
    require_independent(oracles)
    admitted = tuple(admit(e, witnesses[e.relation], policy) for e in frontier.values())
    standing = derive(
        admitted_count=len(admitted),
        hard_failure=hard_failure,
        calibration_complete=len(frontier) == 4,
    )
    if standing is Standing.BUILD_BROKEN:
        return Qualification(None, standing, None)
    bundle = compare(admitted)
    selected = tuple(sorted(r.value for r in bundle.strongest))
    subject = admitted[0].subject.key if admitted else "UNKNOWN"
    receipt = (
        Receipt(subject, max(e.generation for e in admitted), selected, standing)
        if admitted
        else None
    )
    return Qualification(bundle, standing, receipt)
