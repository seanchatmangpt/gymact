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
from gymact.maximal import explore_combinatorial_maximum


def _node(name: str) -> PossibilityObject:
    return PossibilityObject(
        object_id=name,
        kind=PossibilityObjectKind.PLAN,
        semantic_ref=f"urn:test:{name}",
    )


def test_only_proven_reversible_edges_enter_reversible_closure() -> None:
    graph = PossibilityGraph(
        objects=(_node("o"), _node("r"), _node("c"), _node("u"), _node("i")),
        morphisms=(
            PossibilityMorphism(
                morphism_id="reversible",
                source_id="o",
                target_id="r",
                kind=MorphismKind.REALIZE,
                phase=DecisionPhase.CONSTRUCT,
                reversal=ReversalClass.REVERSIBLE,
            ),
            PossibilityMorphism(
                morphism_id="compensatable",
                source_id="o",
                target_id="c",
                kind=MorphismKind.REALIZE,
                phase=DecisionPhase.CONSTRUCT,
                reversal=ReversalClass.COMPENSATABLE,
            ),
            PossibilityMorphism(
                morphism_id="unknown",
                source_id="o",
                target_id="u",
                kind=MorphismKind.REALIZE,
                phase=DecisionPhase.CONSTRUCT,
                reversal=ReversalClass.UNKNOWN,
            ),
            PossibilityMorphism(
                morphism_id="irreversible",
                source_id="o",
                target_id="i",
                kind=MorphismKind.REALIZE,
                phase=DecisionPhase.CONSTRUCT,
                reversal=ReversalClass.IRREVERSIBLE,
            ),
        ),
    )
    result = explore_combinatorial_maximum(graph, start_ids=("o",))
    assert {path.object_ids[-1] for path in result.paths} == {"r"}
    reasons = {item.reason for item in result.evaluations}
    assert "COMPENSATION_IS_NOT_REVERSIBILITY" in reasons
    assert "REVERSIBILITY_NOT_ADMITTED" in reasons
    assert "IRREVERSIBLE_EDGE_REQUIRES_CUT" in reasons


def test_do_is_frontier_even_when_declared_irreversible() -> None:
    graph = PossibilityGraph(
        objects=(_node("o"), _node("effect")),
        morphisms=(
            PossibilityMorphism(
                morphism_id="do",
                source_id="o",
                target_id="effect",
                kind=MorphismKind.ACTUATE,
                phase=DecisionPhase.DO,
                reversal=ReversalClass.IRREVERSIBLE,
                requirements=MorphismRequirements(execution_grant_required=True),
            ),
        ),
    )
    result = explore_combinatorial_maximum(graph, start_ids=("o",))
    assert result.paths == ()
    assert len(result.irreversible_frontier) == 1
    assert result.irreversible_frontier[0].morphism_id == "do"
