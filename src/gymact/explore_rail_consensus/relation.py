from dataclasses import dataclass
from enum import Enum

from .observation import RailObservation

class EvidenceRelation(str, Enum):
    SAME_EVIDENCE = "SAME_EVIDENCE"
    CORRELATED = "CORRELATED"
    INDEPENDENT = "INDEPENDENT"
    UNKNOWN = "UNKNOWN"

@dataclass(frozen=True, slots=True)
class IndependenceProof:
    left_fingerprint: str
    right_fingerprint: str
    proof_digest: str
    independent: bool = True

    def matches(self, left: str, right: str) -> bool:
        return {left, right} == {self.left_fingerprint, self.right_fingerprint}

def relation(left: RailObservation, right: RailObservation, proofs: tuple[IndependenceProof, ...] = ()) -> EvidenceRelation:
    if left.evidence_id == right.evidence_id:
        return EvidenceRelation.SAME_EVIDENCE
    for proof in proofs:
        if proof.matches(left.rail.fingerprint, right.rail.fingerprint):
            return EvidenceRelation.INDEPENDENT if proof.independent else EvidenceRelation.CORRELATED
    if left.rail.family == right.rail.family:
        return EvidenceRelation.CORRELATED
    if left.rail.domain == right.rail.domain and left.rail.toolchain == right.rail.toolchain:
        return EvidenceRelation.CORRELATED
    return EvidenceRelation.UNKNOWN
