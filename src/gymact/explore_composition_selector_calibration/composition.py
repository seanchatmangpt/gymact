from dataclasses import dataclass
from enum import Enum
from .interval import Interval
from .provenance import Provenance, require_independent
from .refusals import Refused

class CompositionMode(str, Enum):
    CONSERVATIVE = "CONSERVATIVE"
    INDEPENDENT = "INDEPENDENT"

@dataclass(frozen=True)
class Evidence:
    evidence_id: str
    interval: Interval
    provenance: Provenance
    generation: int


def compose(left: Evidence, right: Evidence, mode: CompositionMode) -> Interval:
    if left.evidence_id == right.evidence_id:
        raise Refused("DUPLICATE_EVIDENCE")
    if mode is CompositionMode.CONSERVATIVE:
        return left.interval.frechet_and(right.interval)
    require_independent(left.provenance, right.provenance)
    return left.interval.independent_and(right.interval)
