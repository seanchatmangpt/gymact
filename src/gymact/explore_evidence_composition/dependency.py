from __future__ import annotations

from dataclasses import dataclass

from .evidence import EvidenceKind, EvidenceNode
from .refusal import RefusalCode, Refused


@dataclass(frozen=True, slots=True)
class Obligation:
    name: str
    required_kinds: frozenset[EvidenceKind]
    min_generation: int = 0


def discharge(obligation: Obligation, evidence: tuple[EvidenceNode, ...]) -> tuple[EvidenceNode, ...]:
    matched = tuple(
        node
        for node in evidence
        if node.kind in obligation.required_kinds and node.generation >= obligation.min_generation
    )
    present = {node.kind for node in matched}
    missing = obligation.required_kinds - present
    if missing:
        names = ",".join(sorted(kind.value for kind in missing))
        raise Refused(RefusalCode.UNSATISFIED_DEPENDENCY, f"{obligation.name}: missing {names}")
    return matched
