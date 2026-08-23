from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from .loss import LossVector
from .representation import RepresentationCandidate
from .subject import Refusal


@dataclass(frozen=True, slots=True)
class Converter:
    name: str
    source: RepresentationCandidate
    target: RepresentationCandidate
    loss: LossVector
    compute_cost: int

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise Refusal("REFUSED_ANONYMOUS_CONVERTER")
        if self.compute_cost <= 0:
            raise Refusal("REFUSED_INVALID_CONVERTER_COST")
        if self.source.semantic_type.iri != self.target.semantic_type.iri:
            raise Refusal("REFUSED_CROSS_SEMANTIC_CONVERSION")

    @property
    def fingerprint(self) -> str:
        payload = (
            self.name,
            self.source.fingerprint,
            self.target.fingerprint,
            tuple(str(v) for v in self.loss.components),
            self.compute_cost,
        )
        return hashlib.sha256(json.dumps(payload, separators=(",", ":")).encode()).hexdigest()
