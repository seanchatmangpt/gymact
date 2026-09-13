from __future__ import annotations

from gymact.action_contract import ReversalClass
from gymact.combinatorial import (
    AdmissionContext,
    DecisionPhase,
    MorphismKind,
    MorphismRequirements,
    PossibilityGraph,
    PossibilityMorphism,
    PossibilityObject,
    PossibilityObjectKind,
)
from gymact.consequence_binding import ConsequenceBinding, consequence_binding_attributes
from gymact.maximal import explore_combinatorial_maximum


def _node(name: str) -> PossibilityObject:
    return PossibilityObject(
        object_id=name,
        kind=PossibilityObjectKind.PLAN,
        semantic_ref=f"urn:test:{name}",
    )


def _do(attributes: dict[str, object] | None = None) -> PossibilityMorphism:
    return PossibilityMorphism(
        morphism_id="do",
        source_id="source",
        target_id="effect",
        kind=MorphismKind.ACTUATE,
        phase=DecisionPhase.DO,
        reversal=ReversalClass.IRREVERSIBLE,
        requirements=MorphismRequirements(execution_grant_required=True),
        attributes=attributes or {},
    )


def test_do_without_semantic_consequence_binding_is_topology_but_not_admitted() -> None:
    graph = PossibilityGraph(
        objects=(_node("source"), _node("effect")),
        morphisms=(_do(),),
    )
    result = explore_combinatorial_maximum(
        graph,
        start_ids=("source",),
        context=AdmissionContext(execution_grant_ref="urn:grant:present"),
    )
    assert len(result.irreversible_frontier) == 1
    frontier = result.irreversible_frontier[0]
    assert frontier.morphism_id == "do"
    assert frontier.admitted is False
    assert frontier.reason == "DO_SEMANTIC_BINDING_REQUIRED"
    assert graph.morphism("do") == _do()


def test_exact_semantic_binding_allows_frontier_admission_but_not_traversal() -> None:
    binding = ConsequenceBinding(
        action_ref="urn:action:test",
        subject_ref="urn:subject:test",
        capability_ref="urn:capability:test",
        verifier_ref="urn:verifier:test",
        expected_effect_digest="effect-digest",
    )
    edge = _do(consequence_binding_attributes(binding))
    graph = PossibilityGraph(
        objects=(_node("source"), _node("effect")),
        morphisms=(edge,),
    )
    result = explore_combinatorial_maximum(
        graph,
        start_ids=("source",),
        context=AdmissionContext(execution_grant_ref="urn:grant:present"),
    )
    assert result.paths == ()
    assert len(result.irreversible_frontier) == 1
    assert result.irreversible_frontier[0].admitted is True
