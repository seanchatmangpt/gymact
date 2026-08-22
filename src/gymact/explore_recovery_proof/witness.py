from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .subject import Refusal


class WitnessKind(StrEnum):
    EXACT = "EXACT"
    SEMANTIC_EQUIVALENT = "SEMANTIC_EQUIVALENT"
    BACKWARD_COMPATIBLE = "BACKWARD_COMPATIBLE"


@dataclass(frozen=True, slots=True)
class CompatibilityWitness:
    kind: WitnessKind
    before_fingerprint: str
    after_fingerprint: str
    evidence_digest: str

    def __post_init__(self) -> None:
        for value in (self.before_fingerprint, self.after_fingerprint, self.evidence_digest):
            if len(value) != 64:
                raise Refusal("REFUSED_INVALID_COMPATIBILITY_WITNESS")
            try:
                int(value, 16)
            except ValueError as exc:
                raise Refusal("REFUSED_INVALID_COMPATIBILITY_WITNESS") from exc
        if self.kind is WitnessKind.EXACT and self.before_fingerprint != self.after_fingerprint:
            raise Refusal("REFUSED_FALSE_EXACT_WITNESS")
