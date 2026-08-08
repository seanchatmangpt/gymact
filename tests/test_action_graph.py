from __future__ import annotations

from gymact.action_contract import (
    ActionDefinition,
    AuthorityRequirement,
    ExpectedEffect,
    ReversalClass,
    SubjectRef,
    VerificationKind,
    VerificationStrategy,
)
from gymact.action_graph import action_possibility_fragment
from gymact.combinatorial import (
    AdmissionContext,
    DecisionPhase,
    PossibilityObjectKind,
    explore_maximal_reversible,
)


def action() -> ActionDefinition:
    return ActionDefinition(
        semantic_id="urn:action:set",
        provider_ref="urn:provider:memory",
        capability_ref="urn:capability:set",
        subject_type="schema:Thing",
        input_schema={"type": "object"},
        authority=AuthorityRequirement(
            capability_refs=("urn:capability:extra",),
            policy_refs=("urn:policy:auto",),
        ),
        expected_effects=(ExpectedEffect(predicate="state", parameters={"x": 2}),),
        verification=VerificationStrategy(
            kind=VerificationKind.EXACT_STATE,
            observer_ref="urn:verifier:memory",
            expected={"x": 2},
        ),
        reversal=ReversalClass.REVERSIBLE,
    )


def test_action_fragment_is_subject_rooted_and_do_is_frontier() -> None:
    subject = SubjectRef(
        semantic_id="urn:subject:1",
        provider_ref="memory-env",
        revision="rev-1",
    )
    graph = action_possibility_fragment(action(), subject)
    by_kind = {item.kind for item in graph.objects}
    assert {
        PossibilityObjectKind.SUBJECT,
        PossibilityObjectKind.PROVIDER,
        PossibilityObjectKind.CAPABILITY,
        PossibilityObjectKind.ACTION,
        PossibilityObjectKind.VERIFIER,
        PossibilityObjectKind.RECEIPT,
    } <= by_kind
    start = next(item for item in graph.objects if item.kind is PossibilityObjectKind.SUBJECT)
    result = explore_maximal_reversible(
        graph,
        start_ids=(start.object_id,),
        context=AdmissionContext(
            capability_refs=("urn:capability:set", "urn:capability:extra"),
            policy_refs=("urn:policy:auto",),
            current_revision="rev-1",
            execution_grant_ref="urn:grant:admitted",
        ),
    )
    assert len(result.irreversible_frontier) == 1
    frontier = result.irreversible_frontier[0]
    assert frontier.admitted
    do_edge = next(item for item in graph.morphisms if item.phase is DecisionPhase.DO)
    assert frontier.morphism_id == do_edge.morphism_id
    assert not any(path.object_ids[-1] == do_edge.target_id for path in result.paths)


def test_union_preserves_multiple_action_alternatives_for_same_subject() -> None:
    subject = SubjectRef(semantic_id="urn:subject:1", provider_ref="memory-env")
    first = action_possibility_fragment(action(), subject)
    second_action = action().model_copy(
        update={
            "semantic_id": "urn:action:set-alternate",
            "provider_ref": "urn:provider:alternate",
            "capability_ref": "urn:capability:set-alternate",
            "authority": AuthorityRequirement(),
        }
    )
    second = action_possibility_fragment(second_action, subject)
    graph = first.union(second)
    actions = [item for item in graph.objects if item.kind is PossibilityObjectKind.ACTION]
    providers = [item for item in graph.objects if item.kind is PossibilityObjectKind.PROVIDER]
    assert {item.semantic_ref for item in actions} == {
        "urn:action:set",
        "urn:action:set-alternate",
    }
    assert {item.semantic_ref for item in providers} == {
        "urn:provider:memory",
        "urn:provider:alternate",
    }
