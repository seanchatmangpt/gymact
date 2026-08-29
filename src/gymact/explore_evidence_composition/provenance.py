from __future__ import annotations

from dataclasses import dataclass

from .evidence import EvidenceNode
from .refusal import RefusalCode, Refused


@dataclass(frozen=True, slots=True)
class IndependenceWitness:
    left_id: str
    right_id: str
    implementation_distinct: bool
    model_distinct: bool
    source_domain_distinct: bool

    @property
    def admitted(self) -> bool:
        return self.implementation_distinct and self.model_distinct and self.source_domain_distinct


def witness(left: EvidenceNode, right: EvidenceNode) -> IndependenceWitness:
    if not left.same_subject(right):
        raise Refused(RefusalCode.INDEPENDENCE_COLLISION, "foreign-subject evidence cannot establish independence")
    result = IndependenceWitness(
        left.evidence_id,
        right.evidence_id,
        left.implementation_digest != right.implementation_digest,
        left.model_digest != right.model_digest,
        left.source_domain != right.source_domain,
    )
    if not result.admitted:
        raise Refused(RefusalCode.INDEPENDENCE_COLLISION, "implementation/model/source-domain independence not proved")
    return result
