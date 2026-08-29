from __future__ import annotations

from dataclasses import dataclass
from .refusal import Refused

@dataclass(frozen=True)
class Provenance:
    implementation: str
    model: str
    runtime: str


def require_independent(left: Provenance, right: Provenance) -> None:
    shared = []
    if left.implementation == right.implementation: shared.append("implementation")
    if left.model == right.model: shared.append("model")
    if shared:
        raise Refused("COMMON_CAUSE_EVIDENCE", ",".join(shared))
