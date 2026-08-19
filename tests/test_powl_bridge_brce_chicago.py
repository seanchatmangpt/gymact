"""Production POWL -> BRCE -> provider -> verification integration crown."""
from __future__ import annotations

import pytest

from gymact.action_contract import (
    ActionDefinition,
    ExecutionGrant,
    ExpectedEffect,
    SubjectRef,
    VerificationKind,
    VerificationStrategy,
    construct_prepared_action,
)
from gymact.authority import AllowListAuthorityResolver
from gymact.brce import BRCEBroker, BrokerRequest
from gymact.models import MaterializationIntent, Standing
from gymact.powl.algebra import Atom, NodeId, OrderEdge, PartialOrder
from gymact.powl.turtle_bridge import model_to_turtle, powl_node_to_model
from gymact.powl_bridge import parse_admitted_powl_document, replay_admitted_powl_via_brce
from gymact.providers import MemoryProvider
from gymact.runtime import ProductionGymAct

AUTHORITY = "urn:gymact:test:powl-brce:authority"
SET_CAPABILITY = "urn:gymact:memory:capability:set"
INCREMENT_CAPABILITY = "urn:gymact:memory:capability:increment"
SET_ACTION = "urn:gymact:test:powl-brce:action:set"
INCREMENT_ACTION = "urn:gymact:test:powl-brce:action:increment"


def _document() -> str:
    node = PartialOrder(
        (
            Atom(label="set", action=SET_ACTION),
            Atom(label="increment", action=INCREMENT_ACTION),
        ),
        frozenset({OrderEdge(NodeId(0), NodeId(1))}),
    )
    return model_to_turtle(powl_node_to_model(node))


def _request(
    *,
    episode_id: str,
    action_ref: str,
    capability_ref: str,
    payload: dict[str, object],
    expected: dict[str, object],
    key: str,
) -> BrokerRequest:
    effect = ExpectedEffect(predicate="state", parameters=expected)
    action = ActionDefinition(
        semantic_id=action_ref,
        provider_ref="urn:gymact:provider:memory",
        capability_ref=capability_ref,
        subject_type="schema:Thing",
        input_schema={"type": "object"},
        expected_effects=(effect,),
        verification=VerificationStrategy(
            kind=VerificationKind.EXACT_STATE,
            observer_ref="urn:gymact:observer:memory",
            expected=expected,
        ),
    )
    subject = SubjectRef(
        semantic_id=f"urn:gymact:episode:{episode_id}",
        provider_ref="memory",
    )
    prepared = construct_prepared_action(
        action,
        episode_id=episode_id,
        subject=subject,
        payload=payload,
        admission_digest=f"admitted:{key}",
        idempotency_key=key,
    )
    grant = ExecutionGrant(
        principal="urn:gymact:test:principal",
        action_ref=action.semantic_id,
        subject=subject,
        capability_ref=capability_ref,
        authority_ref=AUTHORITY,
        policy_revision="test-policy-v1",
        admitted_observation_ref=f"urn:gymact:test:observation:{key}",
        intended_effects=action.expected_effects,
        nonce=f"nonce:{key}",
    )
    return BrokerRequest(
        action=action,
        prepared=prepared,
        grant=grant,
        expected=expected,
    )


@pytest.mark.asyncio
async def test_real_powl_replay_is_brce_exclusive_and_crowns_only_verified_transitions() -> None:
    runtime = ProductionGymAct(
        validate_profile=False,
        authority_resolver=AllowListAuthorityResolver({AUTHORITY}),
    )
    runtime.register_provider(MemoryProvider())
    materialized = await runtime.materialize(
        MaterializationIntent(
            provider="memory",
            config={"requires_authority": True},
            idempotency_key="powl-brce-materialize",
        )
    )
    assert materialized.episode is not None
    episode_id = materialized.episode.episode_id

    tree = parse_admitted_powl_document(_document())
    transitions = await replay_admitted_powl_via_brce(
        BRCEBroker(runtime),
        tree,
        request_binding={
            SET_ACTION: _request(
                episode_id=episode_id,
                action_ref=SET_ACTION,
                capability_ref=SET_CAPABILITY,
                payload={"key": "counter", "value": 10},
                expected={"counter": 10},
                key="powl-brce-set",
            ),
            INCREMENT_ACTION: _request(
                episode_id=episode_id,
                action_ref=INCREMENT_ACTION,
                capability_ref=INCREMENT_CAPABILITY,
                payload={"key": "counter", "amount": 5},
                expected={"counter": 15},
                key="powl-brce-increment",
            ),
        },
    )

    assert [transition.standing for transition in transitions] == [Standing.ALIVE, Standing.ALIVE]
    assert all(transition.verification is not None for transition in transitions)
    assert all(transition.verification.passed for transition in transitions if transition.verification)
    assert all(transition.receipt.verified is True for transition in transitions)
    assert all(transition.receipt.principal == "urn:gymact:test:principal" for transition in transitions)
    assert (await runtime.observe(episode_id)).state == {"counter": 15}
    assert runtime.verify_evidence_chain()
