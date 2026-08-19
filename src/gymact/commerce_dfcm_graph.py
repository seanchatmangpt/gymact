"""Powerless DfCM possibility graph for the Post-AGI commerce closure.

The execution provider exposes 25 bounded internal capabilities, but DfCM must
preserve an earlier authority distinction: SELECT and CONSTRUCT remain reversible
exploration, while every DO edge is an irreversible frontier until an explicit
execution decision is made. Five DO edges are bounded internal BRCE operations;
seven are marketplace/legal external authority and never enter the commerce gym.
"""

from __future__ import annotations

from gymact.action_contract import ReversalClass
from gymact.combinatorial import (
    AdmissionContext,
    DecisionPhase,
    ExplorationBounds,
    ExplorationResult,
    MorphismKind,
    MorphismRequirements,
    PossibilityGraph,
    PossibilityMorphism,
    PossibilityObject,
    PossibilityObjectKind,
    explore_maximal_reversible,
)
from gymact.gyms.commerce_dfcm import CAPABILITIES, OperationKind
from gymact.models import FrozenModel, Standing

_ROOT_ID = "commerce:subject"
_INTERNAL_POLICY = "urn:gymact:commerce-dfcm:policy:bounded-internal"
_EXTERNAL_POLICY = "urn:gymact:commerce-dfcm:policy:external-authority"


class CommerceDfcmFrontier(FrozenModel):
    """Exact authority partition projected from the canonical possibility graph."""

    graph_digest: str
    semantic_capability_count: int
    reversible_capability_count: int
    do_frontier_count: int
    bounded_internal_do_count: int
    external_do_count: int
    reversible_bindings: tuple[str, ...]
    bounded_internal_do_bindings: tuple[str, ...]
    external_do_bindings: tuple[str, ...]
    exploration: ExplorationResult


def _phase(operation: OperationKind) -> DecisionPhase:
    return DecisionPhase(operation.value)


def _object_id(binding: str) -> str:
    return f"commerce:capability:{binding}"


def commerce_possibility_graph() -> PossibilityGraph:
    """Manufacture the complete 32-capability powerless commerce graph."""
    objects = [
        PossibilityObject(
            object_id=_ROOT_ID,
            kind=PossibilityObjectKind.SUBJECT,
            semantic_ref="urn:gymact:commerce-dfcm:subject:fortune-5-commerce",
            standing=Standing.CANDIDATE,
            attributes={
                "provider": "commerce-dfcm",
                "semantic_capability_count": 32,
            },
        )
    ]
    morphisms: list[PossibilityMorphism] = []

    for capability in CAPABILITIES:
        binding = capability.capability_id
        phase = _phase(capability.operation_kind)
        external = bool(capability.external_authority_required)
        objects.append(
            PossibilityObject(
                object_id=_object_id(binding),
                kind=PossibilityObjectKind.CAPABILITY,
                semantic_ref=f"urn:gymact:commerce-dfcm:capability:{binding}",
                standing=Standing.CANDIDATE,
                attributes={
                    "binding": binding,
                    "external_authority_required": external,
                    "reversible": capability.reversible,
                    "operation_kind": capability.operation_kind.value,
                },
            )
        )
        do_edge = phase is DecisionPhase.DO
        policy_refs: tuple[str, ...] = ()
        if do_edge:
            policy_refs = (_EXTERNAL_POLICY if external else _INTERNAL_POLICY,)
        morphisms.append(
            PossibilityMorphism(
                morphism_id=f"commerce:morphism:{binding}",
                source_id=_ROOT_ID,
                target_id=_object_id(binding),
                kind=MorphismKind.ACTUATE if do_edge else MorphismKind.PROJECT,
                phase=phase,
                reversal=(
                    ReversalClass.REVERSIBLE
                    if capability.reversible
                    else ReversalClass.IRREVERSIBLE
                ),
                requirements=MorphismRequirements(
                    policy_refs=policy_refs,
                    execution_grant_required=do_edge,
                ),
                standing=Standing.CANDIDATE,
                attributes={
                    "binding": binding,
                    "external_authority_required": external,
                },
            )
        )

    return PossibilityGraph(objects=tuple(objects), morphisms=tuple(morphisms))


def commerce_dfcm_frontier() -> CommerceDfcmFrontier:
    """Explore maximal reversible closure and expose all DO cuts without crossing them."""
    graph = commerce_possibility_graph()
    exploration = explore_maximal_reversible(
        graph,
        start_ids=(_ROOT_ID,),
        context=AdmissionContext(),
        bounds=ExplorationBounds(max_depth=2, max_paths=64),
    )

    by_morphism = {item.morphism_id: item for item in graph.morphisms}
    reversible = sorted(
        edge.attributes["binding"]
        for edge in graph.morphisms
        if edge.phase is not DecisionPhase.DO
    )
    bounded_internal_do = sorted(
        edge.attributes["binding"]
        for edge in graph.morphisms
        if edge.phase is DecisionPhase.DO
        and not edge.attributes["external_authority_required"]
    )
    external_do = sorted(
        edge.attributes["binding"]
        for edge in graph.morphisms
        if edge.phase is DecisionPhase.DO
        and edge.attributes["external_authority_required"]
    )

    frontier_ids = {item.morphism_id for item in exploration.irreversible_frontier}
    expected_do_ids = {
        edge.morphism_id for edge in graph.morphisms if edge.phase is DecisionPhase.DO
    }
    if frontier_ids != expected_do_ids:
        raise RuntimeError("COMMERCE_DFCM_IRREVERSIBLE_FRONTIER_INCOMPLETE")
    if any(by_morphism[item].phase is not DecisionPhase.DO for item in frontier_ids):
        raise RuntimeError("COMMERCE_DFCM_NON_DO_ENTERED_IRREVERSIBLE_FRONTIER")

    return CommerceDfcmFrontier(
        graph_digest=graph.graph_digest,
        semantic_capability_count=len(CAPABILITIES),
        reversible_capability_count=len(reversible),
        do_frontier_count=len(frontier_ids),
        bounded_internal_do_count=len(bounded_internal_do),
        external_do_count=len(external_do),
        reversible_bindings=tuple(reversible),
        bounded_internal_do_bindings=tuple(bounded_internal_do),
        external_do_bindings=tuple(external_do),
        exploration=exploration,
    )
