from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from .contracts import OUTCOMES, Refusal, Subject

@dataclass(frozen=True)
class EvidenceCluster:
    cluster_id: str
    source_ids: tuple[str, ...]
    def __post_init__(self) -> None:
        if not self.cluster_id or not self.source_ids or len(set(self.source_ids)) != len(self.source_ids):
            raise Refusal("REFUSED_INVALID_EVIDENCE_CLUSTER")

@dataclass(frozen=True)
class CurrentWitness:
    evidence_id: str
    subject: Subject
    cluster_id: str
    source_id: str
    outcome: str
    observed_at: datetime
    def __post_init__(self) -> None:
        if not self.evidence_id or self.outcome not in OUTCOMES:
            raise Refusal("REFUSED_INVALID_WITNESS")
        if self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise Refusal("REFUSED_NAIVE_WITNESS_TIME")
