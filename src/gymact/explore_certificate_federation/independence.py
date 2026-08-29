from dataclasses import dataclass

from .refusal import FederationRefusal


@dataclass(frozen=True)
class ValidatorIdentity:
    implementation: str
    model: str
    evidence_root: str


def require_independent(validators: tuple[ValidatorIdentity, ...], minimum: int = 2) -> None:
    if minimum < 1:
        raise FederationRefusal("INVALID_QUORUM")
    unique = {(v.implementation, v.model, v.evidence_root) for v in validators}
    if len(unique) < minimum:
        raise FederationRefusal("PSEUDO_INDEPENDENCE")
