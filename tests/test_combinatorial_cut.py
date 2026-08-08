from __future__ import annotations

import pytest

from gymact.action_contract import (
    ActionDefinition,
    ExecutionGrant,
    ExpectedEffect,
    PreparedAction,
    SubjectRef,
    VerificationKind,
    VerificationStrategy,
)
from gymact.combinatorial import (
    AdmissionContext,
    DecisionPhase,
    MorphismKind,
    MorphismRequirements,
    PossibilityGraph,
    PossibilityMorphism,
    PossibilityObject,
    PossibilityObjectKind,
    explore_maximal_reversible,
)
from gymact.cut import manufacture_broker_request, select_irreversible_cut


def fixture() -> tuple[PossibilityGraph, ActionDefinition, PreparedAction, ExecutionGrant]:
    effect = ExpectedEffect(predicate="state", parameters={"x": 2})
    action = ActionDefinition(
        semantic_id="urn:action:set-x",
        provider_ref="urn:provider:memory",
        capability_ref="urn:gymact:memory:capability:set",
        subject_type="schema:Thing",
        input_schema={"type": "object"},
        expected_effects=(effect,),
        verification=VerificationStrategy(
            kind=VerificationKind.EXACT_STATE,
            observer_ref="urn:observer:memory",
            expected={"x": 2},
        ),
    )
    subject = SubjectRef(
        semantic_id="urn:subject:memory",
        provider_ref="memory-env",
        revision="rev-1",
    )
    prepared = PreparedAction(
        episode_id="episode",
        action_ref=action.semantic_id,
        subject=subject,
        payload={"key": "x", "value": 2},
        admission_digest="observation-1",
        idempotency_key="set-x",
    )
    grant = ExecutionGrant(
        principal="urn:principal:test",
        action_ref=action.semantic_id,
        subject=subject,
        capability_ref=action.capability_ref,
        authority_ref="urn:authority:test",
        policy_revision="policy-1",
        admitted_observation_ref="observation-1",
        intended_effects=(effect,),
        nonce="nonce-1",
    )
    graph = PossibilityGraph(
        objects=(
            PossibilityObject(
                object_id="observation",
                kind=PossibilityObjectKind.ADMITTED_OBSERVATION,
                semantic_ref="urn:observation:1",
            ),
            PossibilityObject(
                object_id="plan-a",
                kind=PossibilityObjectKind.PLAN,
                semantic_ref="urn:plan:a",
            ),
            PossibilityObject(
                object_id="plan-b",
                kind=PossibilityObjectKind.PLAN,
                semantic_ref="urn:plan:b",
            ),
            PossibilityObject(
                object_id="effect-a",
                kind=PossibilityObjectKind.RECEIPT,
                semantic_ref="urn:effect:a",
            ),
            PossibilityObject(
                object_id="effect-b",
                kind=PossibilityObjectKind.RECEIPT,
                semantic_ref="urn:effect:b",
            ),
        ),
        morphisms=(
            PossibilityMorphism(
                morphism_id="construct-a",
                source_id="observation",
                target_id="plan-a",
                kind=MorphismKind.PLAN,
                phase=DecisionPhase.CONSTRUCT,
            ),
            PossibilityMorphism(
                morphism_id="construct-b",
                source_id="observation",
                target_id="plan-b",
                kind=MorphismKind.PLAN,
                phase=DecisionPhase.CONSTRUCT,
            ),
            PossibilityMorphism(
                morphism_id="do-a",
                source_id="plan-a",
                target_id="effect-a",
                kind=MorphismKind.ACTUATE,
                phase=DecisionPhase.DO,
                requirements=MorphismRequirements(execution_grant_required=True),
            ),
            PossibilityMorphism(
                morphism_id="do-b",
                source_id="plan-b",
                target_id="effect-b",
                kind=MorphismKind.ACTUATE,
                phase=DecisionPhase.DO,
                requirements=MorphismRequirements(execution_grant_required=True),
            ),
        ),
    )
    return graph, action, prepared, grant


def test_cut_refuses_frontier_that_was_not_authority_admitted() -> None:
    graph, action, prepared, grant = fixture()
    exploration = explore_maximal_reversible(graph, start_ids=("observation",))
    frontier = next(item for item in exploration.irreversible_frontier if item.morphism_id == "do-a")
    assert not frontier.admitted
    with pytest.raises(ValueError, match="IRREVERSIBLE_FRONTIER_NOT_ADMITTED"):
        select_irreversible_cut(
            graph,
            exploration,
            path_id=frontier.path_id,
            morphism_id=frontier.morphism_id,
            action=action,
            prepared=prepared,
            grant=grant,
            selector_ref="urn:selector:test",
            current_revision="rev-1",
        )


def test_cut_binds_exact_graph_path_grant_and_prepared_identity() -> None:
    graph, action, prepared, grant = fixture()
    exploration = explore_maximal_reversible(
        graph,
        start_ids=("observation",),
        context=AdmissionContext(
            current_revision="rev-1",
            execution_grant_ref="urn:grant:admitted",
        ),
    )
    assert {item.morphism_id for item in exploration.irreversible_frontier} == {"do-a", "do-b"}
    selected = next(item for item in exploration.irreversible_frontier if item.morphism_id == "do-a")
    cut = select_irreversible_cut(
        graph,
        exploration,
        path_id=selected.path_id,
        morphism_id=selected.morphism_id,
        action=action,
        prepared=prepared,
        grant=grant,
        selector_ref="urn:selector:pareto-court",
        basis_refs=("urn:evidence:benchmark-1",),
        current_revision="rev-1",
    )
    assert cut.verify_digest()
    request = manufacture_broker_request(
        cut,
        action=action,
        prepared=prepared,
        grant=grant,
        current_revision="rev-1",
        expected={"x": 2},
    )
    assert request.selection.selection_digest == cut.selection_digest
    assert request.broker_request.prepared == prepared
    assert request.broker_request.grant == grant


def test_cut_detects_prepared_and_grant_drift_before_brce() -> None:
    graph, action, prepared, grant = fixture()
    exploration = explore_maximal_reversible(
        graph,
        start_ids=("observation",),
        context=AdmissionContext(execution_grant_ref="urn:grant:admitted"),
    )
    selected = next(item for item in exploration.irreversible_frontier if item.morphism_id == "do-a")
    cut = select_irreversible_cut(
        graph,
        exploration,
        path_id=selected.path_id,
        morphism_id=selected.morphism_id,
        action=action,
        prepared=prepared,
        grant=grant,
        selector_ref="urn:selector:test",
    )
    changed = prepared.model_copy(update={"payload": {"key": "x", "value": 3}})
    with pytest.raises(ValueError, match="IRREVERSIBLE_SELECTION_PREPARED_DRIFT"):
        manufacture_broker_request(
            cut,
            action=action,
            prepared=changed,
            grant=grant,
        )
    changed_grant = grant.model_copy(update={"nonce": "nonce-2"})
    with pytest.raises(ValueError, match="IRREVERSIBLE_SELECTION_GRANT_DRIFT"):
        manufacture_broker_request(
            cut,
            action=action,
            prepared=prepared,
            grant=changed_grant,
        )
