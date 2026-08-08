"""Canonical Design for Combinatorial Maximum closure.

This is the strict explorer. It preserves every graph edge as topology, but traverses
only morphisms whose reversibility is mechanically admitted. Unknown or irreversible
non-DO edges become explicit frontier/fence evidence rather than silently entering the
reversible closure.
"""
from __future__ import annotations

from typing import Iterable

from gymact.action_contract import ReversalClass
from gymact.combinatorial import (
    AdmissionContext,
    DecisionPhase,
    ExplorationBounds,
    ExplorationResult,
    IrreversibleFrontierEdge,
    MorphismEvaluation,
    PossibilityGraph,
    PossibilityPath,
    evaluate_morphism,
    pareto_paths,
)
from gymact.models import Standing


def _within_bounds(path: PossibilityPath, bounds: ExplorationBounds) -> bool:
    value = path.objectives
    checks = (
        (value.monetary_cost, bounds.max_monetary_cost),
        (value.wall_time_s, bounds.max_wall_time_s),
        (value.compute_units, bounds.max_compute_units),
        (value.human_interventions, bounds.max_human_interventions),
        (value.risk_score, bounds.max_risk_score),
    )
    return all(limit is None or observed <= limit for observed, limit in checks)


def _reversibility_fence(reversal: ReversalClass) -> str:
    return {
        ReversalClass.COMPENSATABLE: "COMPENSATION_IS_NOT_REVERSIBILITY",
        ReversalClass.IRREVERSIBLE: "IRREVERSIBLE_EDGE_REQUIRES_CUT",
        ReversalClass.UNKNOWN: "REVERSIBILITY_NOT_ADMITTED",
    }[reversal]


def explore_combinatorial_maximum(
    graph: PossibilityGraph,
    *,
    start_ids: Iterable[str],
    context: AdmissionContext | None = None,
    bounds: ExplorationBounds | None = None,
) -> ExplorationResult:
    """Compute bounded maximal *proven-reversible* closure and explicit DO frontier.

    Every considered edge/path receives one final traversal disposition. A failed or
    fenced edge remains graph topology but cannot enter the reversible closure.
    """
    ctx = context or AdmissionContext()
    limits = bounds or ExplorationBounds()
    starts = tuple(start_ids)
    for object_id in starts:
        graph.object(object_id)

    stack = [PossibilityPath(object_ids=(item,)) for item in reversed(starts)]
    emitted: list[PossibilityPath] = []
    frontier: list[IrreversibleFrontierEdge] = []
    evaluations: list[MorphismEvaluation] = []
    truncation_reasons: set[str] = set()

    while stack:
        path = stack.pop()
        outgoing = graph.outgoing(path.object_ids[-1])
        if len(path.morphism_ids) >= limits.max_depth:
            if outgoing:
                truncation_reasons.add("MAX_DEPTH")
            continue

        for edge in outgoing:
            admission = evaluate_morphism(edge, ctx)

            if edge.phase is DecisionPhase.DO:
                evaluations.append(admission)
                frontier.append(
                    IrreversibleFrontierEdge(
                        path_id=path.path_id,
                        morphism_id=edge.morphism_id,
                        target_id=edge.target_id,
                        standing=admission.standing,
                        admitted=admission.admitted,
                        reason=admission.reason,
                    )
                )
                continue

            if not admission.admitted:
                evaluations.append(admission)
                continue

            if edge.reversal is not ReversalClass.REVERSIBLE:
                evaluations.append(
                    MorphismEvaluation(
                        morphism_id=edge.morphism_id,
                        standing=Standing.BLOCKED,
                        admitted=False,
                        reason=_reversibility_fence(edge.reversal),
                    )
                )
                continue

            candidate = PossibilityPath(
                object_ids=(*path.object_ids, edge.target_id),
                morphism_ids=(*path.morphism_ids, edge.morphism_id),
                objectives=path.objectives.compose(edge.objectives),
            )
            if not _within_bounds(candidate, limits):
                evaluations.append(
                    MorphismEvaluation(
                        morphism_id=edge.morphism_id,
                        standing=Standing.BLOCKED,
                        admitted=False,
                        reason="EXPLORATION_BOUND_EXCEEDED",
                    )
                )
                continue

            evaluations.append(admission)
            if len(emitted) >= limits.max_paths:
                truncation_reasons.add("MAX_PATHS")
                stack.clear()
                break
            emitted.append(candidate)
            stack.append(candidate)

    pareto = pareto_paths(emitted)
    return ExplorationResult(
        graph_digest=graph.graph_digest,
        start_ids=starts,
        paths=tuple(emitted),
        pareto_path_ids=tuple(path.path_id for path in pareto),
        irreversible_frontier=tuple(frontier),
        evaluations=tuple(evaluations),
        truncated=bool(truncation_reasons),
        truncation_reasons=tuple(sorted(truncation_reasons)),
    )
