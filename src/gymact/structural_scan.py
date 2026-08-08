"""Cheap structural scan for DCM before semantic interpretation or ranking."""
from __future__ import annotations

from collections import Counter

from gymact.action_contract import ReversalClass
from gymact.combinatorial import DecisionPhase, PossibilityGraph
from gymact.evidence import digest
from gymact.models import FrozenModel


class StructuralSignature(FrozenModel):
    graph_digest: str
    object_counts: dict[str, int]
    morphism_counts: dict[str, int]
    phase_counts: dict[str, int]
    standing_counts: dict[str, int]
    reversible_edges: int
    compensatable_edges: int
    unknown_reversal_edges: int
    do_edges: int
    branching_objects: int
    max_out_degree: int
    cyclic: bool
    structural_key: str


def _has_cycle(graph: PossibilityGraph) -> bool:
    adjacency = {
        item.object_id: tuple(edge.target_id for edge in graph.outgoing(item.object_id))
        for item in graph.objects
    }
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str) -> bool:
        if node in visiting:
            return True
        if node in visited:
            return False
        visiting.add(node)
        for target in adjacency[node]:
            if visit(target):
                return True
        visiting.remove(node)
        visited.add(node)
        return False

    return any(visit(item.object_id) for item in graph.objects if item.object_id not in visited)


def structural_scan(graph: PossibilityGraph) -> StructuralSignature:
    """Extract O(n + m) topology before any open-ended semantic reasoning."""
    object_counts = Counter(item.kind.value for item in graph.objects)
    morphism_counts = Counter(item.kind.value for item in graph.morphisms)
    phase_counts = Counter(item.phase.value for item in graph.morphisms)
    standing_counts = Counter(item.standing.value for item in graph.morphisms)
    out_degrees = [len(graph.outgoing(item.object_id)) for item in graph.objects]
    payload = {
        "object_counts": dict(sorted(object_counts.items())),
        "morphism_counts": dict(sorted(morphism_counts.items())),
        "phase_counts": dict(sorted(phase_counts.items())),
        "standing_counts": dict(sorted(standing_counts.items())),
        "reversible_edges": sum(
            item.reversal is ReversalClass.REVERSIBLE for item in graph.morphisms
        ),
        "compensatable_edges": sum(
            item.reversal is ReversalClass.COMPENSATABLE for item in graph.morphisms
        ),
        "unknown_reversal_edges": sum(
            item.reversal is ReversalClass.UNKNOWN for item in graph.morphisms
        ),
        "do_edges": sum(item.phase is DecisionPhase.DO for item in graph.morphisms),
        "branching_objects": sum(value > 1 for value in out_degrees),
        "max_out_degree": max(out_degrees, default=0),
        "cyclic": _has_cycle(graph),
    }
    return StructuralSignature(
        graph_digest=graph.graph_digest,
        **payload,
        structural_key=digest(payload),
    )
