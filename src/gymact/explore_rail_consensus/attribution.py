from dataclasses import dataclass

from .signature import FailureSignature
from .subject import Refusal

@dataclass(frozen=True, slots=True)
class AttributionEdge:
    signature_digest: str
    component: str
    evidence: str
    confidence_basis: str

    def __post_init__(self) -> None:
        if not self.component or not self.evidence or not self.confidence_basis:
            raise Refusal("REFUSED_UNGROUNDED_ATTRIBUTION")

@dataclass(frozen=True, slots=True)
class AttributionGraph:
    signatures: tuple[FailureSignature, ...]
    edges: tuple[AttributionEdge, ...]

    def components_for(self, signature: FailureSignature) -> tuple[str, ...]:
        return tuple(sorted({edge.component for edge in self.edges if edge.signature_digest == signature.digest}))

    def admit_closed(self) -> None:
        known = {sig.digest for sig in self.signatures}
        dangling = [edge.signature_digest for edge in self.edges if edge.signature_digest not in known]
        if dangling:
            raise Refusal("REFUSED_DANGLING_ATTRIBUTION")
