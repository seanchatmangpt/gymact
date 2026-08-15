"""Chicago-style tests for `gymact.powl_bridge`. Real GymAct kernel, real
MemoryProvider, real POWL algebra -> real Turtle serialize -> real Turtle
parse -> real gymact.powl.executor structural replay -> real kernel.act()
calls -- no mocks. Mirrors tests/test_gdmcp_bpmn_bridge_chicago.py's shape
exactly, for the POWL-native bridge instead of the BPMN one.
"""

from __future__ import annotations

import pytest

from gymact.authority import AllowListAuthorityResolver, DenyAuthorityResolver
from gymact.kernel import GymAct
from gymact.models import ActuationIntent, MaterializationIntent
from gymact.powl.algebra import Atom, NodeId, OrderEdge, PartialOrder
from gymact.powl.turtle_bridge import model_to_turtle, powl_node_to_model
from gymact.powl_bridge import (
    PowlReplayRefusal,
    parse_admitted_powl_document,
    replay_admitted_powl_via_kernel,
)
from gymact.providers import MemoryProvider

AUTHORITY = "urn:gymact:test:powl-bridge"
SET_CAPABILITY = "urn:gymact:memory:capability:set"
INCREMENT_CAPABILITY = "urn:gymact:memory:capability:increment"
SET_ACTION = "urn:gymact:test:powl-bridge:action:set"
INCREMENT_ACTION = "urn:gymact:test:powl-bridge:action:increment"


async def _materialized_episode(kernel: GymAct, provider: MemoryProvider) -> str:
    kernel.register_provider(provider)
    result = await kernel.materialize(
        MaterializationIntent(
            provider=provider.name,
            config={"requires_authority": True},
            authority_ref=AUTHORITY,
        )
    )
    assert result.accepted, result.receipt.reason
    assert result.episode is not None
    return result.episode.episode_id


def _real_two_step_document() -> str:
    """A real, ordered two-atom POWL2 document -- exactly the flat total
    order `autofde_lab.fabric.powl.project_plan_to_powl` emits, produced
    here via the real `powl_node_to_model` + `model_to_turtle` round trip
    rather than hand-authored Turtle text, so the fixture stays in lockstep
    with the real serializer's actual output shape."""
    node = PartialOrder(
        (
            Atom(label="step-0", action=SET_ACTION),
            Atom(label="step-1", action=INCREMENT_ACTION),
        ),
        frozenset({OrderEdge(NodeId(0), NodeId(1))}),
    )
    return model_to_turtle(powl_node_to_model(node))


def _real_intent_binding(episode_id: str, authority_ref: str | None) -> dict[str, ActuationIntent]:
    return {
        SET_ACTION: ActuationIntent(
            episode_id=episode_id,
            capability=SET_CAPABILITY,
            payload={"key": "counter", "value": 10},
            authority_ref=authority_ref,
        ),
        INCREMENT_ACTION: ActuationIntent(
            episode_id=episode_id,
            capability=INCREMENT_CAPABILITY,
            payload={"key": "counter", "amount": 5},
            authority_ref=authority_ref,
        ),
    }


def test_parse_admitted_powl_document_round_trips_a_real_algebra_tree():
    turtle = _real_two_step_document()
    tree = parse_admitted_powl_document(turtle)
    assert isinstance(tree, PartialOrder)
    assert [atom.action for atom in tree.children] == [SET_ACTION, INCREMENT_ACTION]


@pytest.mark.asyncio
async def test_real_replay_dispatches_both_intents_in_real_powl_determined_order():
    kernel = GymAct(authority_resolver=AllowListAuthorityResolver({AUTHORITY}))
    provider = MemoryProvider()
    episode_id = await _materialized_episode(kernel, provider)
    tree = parse_admitted_powl_document(_real_two_step_document())
    binding = _real_intent_binding(episode_id, AUTHORITY)

    results = await replay_admitted_powl_via_kernel(kernel, tree, intent_binding=binding)

    assert len(results) == 2
    assert all(r.accepted for r in results)
    assert results[0].effect == {
        "before": {},
        "after": {"counter": 10},
        "capability": SET_CAPABILITY,
    }
    assert results[1].effect == {
        "before": {"counter": 10},
        "after": {"counter": 15},
        "capability": INCREMENT_CAPABILITY,
    }


@pytest.mark.asyncio
async def test_powl_replay_never_bypasses_authority_admission():
    """MCPValidity != DOAuthority, checked directly: real structural replay
    determines a real fire order, but a real DenyAuthorityResolver still
    refuses the actual kernel.act() call -- the bridge never grants
    authority itself."""
    kernel = GymAct(authority_resolver=DenyAuthorityResolver())
    provider = MemoryProvider()
    kernel.register_provider(provider)
    result = await kernel.materialize(
        MaterializationIntent(provider=provider.name, config={"requires_authority": True})
    )
    assert result.accepted, result.receipt.reason
    assert result.episode is not None
    episode_id = result.episode.episode_id

    tree = parse_admitted_powl_document(_real_two_step_document())
    binding = _real_intent_binding(episode_id, AUTHORITY)

    results = await replay_admitted_powl_via_kernel(kernel, tree, intent_binding=binding)

    assert results[0].accepted is False
    assert results[0].receipt.reason == "AUTHORITY_NOT_ADMITTED"


@pytest.mark.asyncio
async def test_unbound_implements_action_is_refused_before_any_kernel_call():
    kernel = GymAct(authority_resolver=AllowListAuthorityResolver({AUTHORITY}))
    provider = MemoryProvider()
    episode_id = await _materialized_episode(kernel, provider)
    tree = parse_admitted_powl_document(_real_two_step_document())

    with pytest.raises(PowlReplayRefusal, match="UNBOUND_IMPLEMENTS_ACTION"):
        await replay_admitted_powl_via_kernel(kernel, tree, intent_binding={})

    observation = await kernel.observe(episode_id)
    assert observation.state == {}


def test_empty_document_is_refused_before_any_real_parse():
    with pytest.raises(PowlReplayRefusal, match="NO_POWL_MODEL|EMPTY_MODEL"):
        parse_admitted_powl_document("@prefix powl2: <https://truex.io/ontology/powl2#> .")
