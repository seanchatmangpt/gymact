from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .interval import Interval
from .subject import Subject


class EvidenceKind(StrEnum):
    SEMANTIC = "SEMANTIC"
    TRACE = "TRACE"
    CALIBRATION = "CALIBRATION"
    METHODOLOGY = "METHODOLOGY"
    RUNTIME = "RUNTIME"
    SECURITY = "SECURITY"
    AUTHORITY = "AUTHORITY"
    REPLAY = "REPLAY"


@dataclass(frozen=True, slots=True)
class EvidenceNode:
    evidence_id: str
    subject: Subject
    kind: EvidenceKind
    generation: int
    confidence: Interval
    implementation_digest: str
    model_digest: str
    source_domain: str
    cost: float = 0.0

    def same_subject(self, other: EvidenceNode) -> bool:
        return self.subject == other.subject
