from dataclasses import dataclass
from .interval import Interval
from .provenance import Provenance
from .subject import Subject
from .refusal import Refused

@dataclass(frozen=True)
class Evidence:
    evidence_id: str
    subject: Subject
    generation: int
    interval: Interval
    provenance: Provenance
    parents: tuple[str, ...] = ()
    cost: int = 1

    def __post_init__(self) -> None:
        if not self.evidence_id or self.generation < 0 or self.cost < 0:
            raise Refused("INVALID_EVIDENCE", self.evidence_id)
        if self.evidence_id in self.parents:
            raise Refused("SELF_PARENT_EVIDENCE", self.evidence_id)
