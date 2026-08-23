from dataclasses import dataclass
from enum import StrEnum

from .capability import RailCapability


class Dependence(StrEnum):
    SAME = "SAME"
    CORRELATED = "CORRELATED"
    INDEPENDENT = "INDEPENDENT"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class IndependenceProof:
    left: str
    right: str
    proof_digest: str

    def matches(self, a: str, b: str) -> bool:
        return {self.left, self.right} == {a, b}


def dependence(
    left: RailCapability,
    right: RailCapability,
    proofs: tuple[IndependenceProof, ...] = (),
) -> Dependence:
    if left.fingerprint == right.fingerprint:
        return Dependence.SAME
    if any(proof.matches(left.fingerprint, right.fingerprint) for proof in proofs):
        return Dependence.INDEPENDENT
    if left.family == right.family or left.domain == right.domain:
        return Dependence.CORRELATED
    return Dependence.UNKNOWN


def independent_set(
    rails: tuple[RailCapability, ...],
    proofs: tuple[IndependenceProof, ...],
) -> bool:
    for index, left in enumerate(rails):
        for right in rails[index + 1 :]:
            if dependence(left, right, proofs) is not Dependence.INDEPENDENT:
                return False
    return True
