from dataclasses import dataclass
from datetime import datetime
from .source import EvidenceSource
OUTCOMES={"PASS","FAIL","PENDING","UNKNOWN","UNSUPPORTED"}
SCOPES={"FOCUSED","REPOSITORY","RUNTIME","ARTIFACT","DEPENDENCY","RECEIPT"}
@dataclass(frozen=True)
class Observation:
    source: EvidenceSource
    scope: str
    outcome: str
    observed_at: datetime
    evidence_id: str
    def __post_init__(self):
        if self.scope not in SCOPES or self.outcome not in OUTCOMES or not self.evidence_id:
            raise ValueError("REFUSED_INVALID_OBSERVATION")
        if self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise ValueError("REFUSED_NAIVE_OBSERVATION_TIME")
