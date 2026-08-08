from __future__ import annotations

from gymact.action_contract import (
    ActionDefinition,
    AuthorityRequirement,
    ExecutionGrant,
    ExpectedEffect,
    ReversalClass,
    SubjectRef,
    VerificationKind,
    VerificationStrategy,
    construct_prepared_action,
)
from gymact.action_graph import action_possibility_fragment
from gymact.combinatorial import AdmissionContext, PossibilityObjectKind
from gymact.dcm_runtime import DCMDecisionCourt


def fixture():
    subject = SubjectRef(
        semantic_id="urn:subject:1",
        provider_ref="provider-subject",
        revision="rev-1",
    )
    effect = ExpectedEffect(predicate="state", parameters={"x": 2})
    action = ActionDefinition(
        semantic_id="urn:action:set",
        provider_ref="urn:provider:memory",
        capability_ref="urn:capability:set",
        subject_type="schema:Thing",
        input_schema={"type": "object"},
        authority=AuthorityRequirement(policy_refs=("urn:policy:auto",)),
        expected_effects=(effect,),
        verification=VerificationStrategy(
            kind=VerificationKind.EXACT_STATE,
            observer_ref="urn:verifier:memory",
            expected={"x": 2},
        ),
        reversal=ReversalClass.REVERSIBLE,
    )
    prepared = construct_prepared_action(
        action,
        episode_id="episode",
        subject=subject,
        payload={"x": 2},
        admission_digest="observation-1",
        idempotency_key="set-1",
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
    graph = action_possibility_fragment(action, subject)
    start = next(item for item in graph.objects if item.kind is PossibilityObjectKind.SUBJECT)
    return graph, start.object_id, action, prepared, grant


def test_court_admits_rdf_scans_structure_and_preserves_do_frontier() -> None:
    graph, start_id, action, prepared, grant = fixture()
    court = DCMDecisionCourt()
    record = court.admit_and_explore(
        graph,
        start_ids=(start_id,),
        context=AdmissionContext(
            capability_refs=(action.capability_ref,),
            policy_refs=("urn:policy:auto",),
            current_revision="rev-1",
            execution_grant_ref="urn:grant:admitted",
        ),
    )
    assert record.rdf_validation.conforms
    assert record.graph_digest == graph.graph_digest
    assert record.structural_signature.graph_digest == graph.graph_digest
    assert record.exploration.truncated is False
    assert len(record.exploration.irreversible_frontier) == 1
    assert record.exploration.irreversible_frontier[0].admitted

    frontier = record.exploration.irreversible_frontier[0]
    selection = court.select(
        graph,
        record,
        path_id=frontier.path_id,
        morphism_id=frontier.morphism_id,
        action=action,
        prepared=prepared,
        grant=grant,
        selector_ref="urn:selector:court",
        basis_refs=("urn:evidence:benchmark",),
        current_revision="rev-1",
    )
    request = court.manufacture_request(
        selection,
        action=action,
        prepared=prepared,
        grant=grant,
        current_revision="rev-1",
        expected={"x": 2},
    )
    assert request.selection.verify_digest()
    assert request.selection.graph_digest == record.graph_digest
