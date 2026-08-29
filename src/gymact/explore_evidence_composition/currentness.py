from __future__ import annotations

from collections import defaultdict

from .evidence import EvidenceNode
from .refusal import RefusalCode, Refused


def current_frontier(nodes: tuple[EvidenceNode, ...]) -> tuple[EvidenceNode, ...]:
    if not nodes:
        return ()
    max_generation = max(node.generation for node in nodes)
    current = tuple(node for node in nodes if node.generation == max_generation)
    by_kind: dict[object, set[tuple[str, str]]] = defaultdict(set)
    for node in current:
        by_kind[node.kind].add((node.implementation_digest, node.model_digest))
    if any(len(identities) > 1 for identities in by_kind.values()):
        raise Refused(RefusalCode.DIVERGENT_FRONTIER, "latest generation has divergent identities for one evidence kind")
    return tuple(sorted(current, key=lambda node: node.evidence_id))


def require_current(node: EvidenceNode, frontier: tuple[EvidenceNode, ...]) -> None:
    if node.evidence_id not in {item.evidence_id for item in frontier}:
        raise Refused(RefusalCode.STALE_EVIDENCE, node.evidence_id)
