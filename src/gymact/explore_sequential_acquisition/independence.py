from dataclasses import dataclass
from .sensor import SensorCapability


@dataclass(frozen=True)
class IndependenceProof:
    left_digest: str
    right_digest: str
    rationale: str

    def admits(self, left: SensorCapability, right: SensorCapability) -> bool:
        expected = {self.left_digest, self.right_digest}
        actual = {left.digest, right.digest}
        return bool(self.rationale.strip()) and expected == actual


def independent(left: SensorCapability, right: SensorCapability, proof: IndependenceProof | None = None) -> bool:
    if left.digest == right.digest:
        return False
    if proof and proof.admits(left, right):
        return True
    return left.independence_key != right.independence_key
