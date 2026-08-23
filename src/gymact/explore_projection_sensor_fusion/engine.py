from dataclasses import dataclass

from .acquisition import AcquisitionCandidate
from .audit import audit_root
from .authority import ActionClass, require_authority
from .budget import Budget
from .calibration import Calibration
from .frontier import current_frontier
from .independence import IndependenceProof
from .pareto import frontier
from .receipt import Receipt
from .selectors import Selector, select
from .subject import Subject
from .topology import FusionTopology, classify


@dataclass(frozen=True, slots=True)
class Qualification:
    topology: FusionTopology
    candidates: tuple[AcquisitionCandidate, ...]
    selected: AcquisitionCandidate | None
    receipt: Receipt


def qualify(subject: Subject, calibrations: tuple[Calibration, ...], proofs: tuple[IndependenceProof, ...], candidates: tuple[AcquisitionCandidate, ...], selector: Selector, budget: Budget, action: ActionClass = ActionClass.CONSTRUCT) -> Qualification:
    require_authority(action)
    current = current_frontier(calibrations)
    topology = classify(current, proofs)
    lawful = tuple(c for c in frontier(candidates) if budget.admits(c))
    selected = select(lawful, selector) if topology is FusionTopology.HEALTHY else None
    standing = "PARTIAL_ALIVE" if selected is not None else "UNKNOWN"
    receipt = Receipt(subject, selector.value, selected.sensor_id if selected else None, audit_root(tuple(c.sensor.calibration_digest for c in current)), standing, action)
    return Qualification(topology, lawful, selected, receipt)
