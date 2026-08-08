from __future__ import annotations

from gymact.action_contract import ReversalClass
from gymact.combinatorial import (
    DecisionPhase,
    MorphismKind,
    MorphismRequirements,
    PossibilityGraph,
    PossibilityMorphism,
    PossibilityObject,
    PossibilityObjectKind,
)
from gymact.structural_scan import structural_scan


def topology(prefix: str) -> PossibilityGraph:
    return PossibilityGraph(
        objects=(
            PossibilityObject(
                object_id=f"{prefix}-o",
                kind=PossibilityObjectKind.ADMITTED_OBSERVATION,
                semantic_ref=f"urn:{prefix}:o",
            ),
            PossibilityObject(
                object_id=f"{prefix}-a",
                kind=PossibilityObjectKind.PLAN,
                semantic_ref=f"urn:{prefix}:a",
            ),
            PossibilityObject(
                object_id=f"{prefix}-b",
                kind=PossibilityObjectKind.RECEIPT,
                semantic_ref=f"urn:{prefix}:b",
            ),
        ),
        morphisms=(
            PossibilityMorphism(
                morphism_id=f"{prefix}-construct",
                source_id=f"{prefix}-o",
                target_id=f"{prefix}-a",
                kind=MorphismKind.PLAN,
                phase=DecisionPhase.CONSTRUCT,
                reversal=ReversalClass.REVERSIBLE,
            ),
            PossibilityMorphism(
                morphism_id=f"{prefix}-do",
                source_id=f"{prefix}-a",
                target_id=f"{prefix}-b",
                kind=MorphismKind.ACTUATE,
                phase=DecisionPhase.DO,
                reversal=ReversalClass.IRREVERSIBLE,
                requirements=MorphismRequirements(execution_grant_required=True),
            ),
        ),
    )


def test_structural_scan_ignores_semantic_names_but_not_content_identity() -> None:
    first = structural_scan(topology("first"))
    second = structural_scan(topology("second"))
    assert first.graph_digest != second.graph_digest
    assert first.structural_key == second.structural_key
    assert first.do_edges == 1
    assert first.reversible_edges == 1
    assert first.max_out_degree == 1
    assert first.cyclic is False


def test_structural_scan_detects_branching_without_semantic_reasoning() -> None:
    graph = topology("branch")
    extra = PossibilityObject(
        object_id="branch-extra",
        kind=PossibilityObjectKind.PLAN,
        semantic_ref="urn:branch:extra",
    )
    graph = graph.with_object(extra).with_morphism(
        PossibilityMorphism(
            morphism_id="branch-second",
            source_id="branch-o",
            target_id="branch-extra",
            kind=MorphismKind.PLAN,
            phase=DecisionPhase.CONSTRUCT,
            reversal=ReversalClass.REVERSIBLE,
        )
    )
    signature = structural_scan(graph)
    assert signature.branching_objects == 1
    assert signature.max_out_degree == 2
