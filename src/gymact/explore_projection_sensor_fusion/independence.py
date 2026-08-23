from dataclasses import dataclass

from .refusals import FusionRefused
from .sensor import SensorIdentity


@dataclass(frozen=True, slots=True)
class IndependenceProof:
    left: SensorIdentity
    right: SensorIdentity
    evidence_digest: str

    def __post_init__(self) -> None:
        if self.left.sensor_id == self.right.sensor_id:
            raise FusionRefused("REFUSED_SELF_INDEPENDENCE")
        if self.left.family == self.right.family or self.left.domain == self.right.domain:
            raise FusionRefused("REFUSED_UNPROVEN_INDEPENDENCE")
        if len(self.evidence_digest) != 64:
            raise FusionRefused("REFUSED_INVALID_INDEPENDENCE_EVIDENCE")

    def pair(self) -> frozenset[str]:
        return frozenset((self.left.sensor_id, self.right.sensor_id))
