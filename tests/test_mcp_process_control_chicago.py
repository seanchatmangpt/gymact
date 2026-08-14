"""Chicago-style tests for `gymact.mcp_process_control.dispatch`. Real
`GymAct` kernel, real `gymact.providers.MemoryProvider`, real
`AllowListAuthorityResolver`/`DenyAuthorityResolver` -- no mocks.

Proves `MCPValidity != DOAuthority` is actually enforced by this module, not
just asserted: graph-licensing is checked BEFORE `kernel.act()` is ever
called, and graph-licensing never substitutes for or bypasses the real
CapabilityScope/AuthorityResolver gates.
"""

from __future__ import annotations

import pytest

from gymact.authority import AllowListAuthorityResolver, DenyAuthorityResolver
from gymact.kernel import GymAct
from gymact.mcp_process_control import DispatchRefusal, ProcessControlGraph, ProcessTransition, dispatch
from gymact.models import MaterializationIntent
from gymact.providers import MemoryProvider

AUTHORITY = "urn:gymact:test:mcp-process-control-authority"
SET_CAPABILITY = "urn:gymact:memory:capability:set"
INCREMENT_CAPABILITY = "urn:gymact:memory:capability:increment"

# set must precede increment -- a real, evaluable two-step chain.
LINEAR_GRAPH = ProcessControlGraph(
    graph_id="urn:gymact:test:linear-set-then-increment",
    transitions=(
        ProcessTransition(from_capability=None, to_capability=SET_CAPABILITY),
        ProcessTransition(from_capability=SET_CAPABILITY, to_capability=INCREMENT_CAPABILITY),
    ),
)


async def _materialized_episode(kernel: GymAct, provider: MemoryProvider) -> str:
    kernel.register_provider(provider)
    result = await kernel.materialize(
        MaterializationIntent(
            provider=provider.name,
            config={"requires_authority": True, "initial": {"counter": 1}},
            authority_ref=AUTHORITY,
        )
    )
    assert result.accepted, result.receipt.reason
    assert result.episode is not None
    return result.episode.episode_id


@pytest.mark.asyncio
async def test_a_licensed_and_authorized_call_succeeds():
    """The first real, load-bearing case: set is licensed as the START
    transition, real AuthorityResolver admits it, real kernel.act() runs."""
    kernel = GymAct(authority_resolver=AllowListAuthorityResolver({AUTHORITY}))
    provider = MemoryProvider()
    episode_id = await _materialized_episode(kernel, provider)

    result = await dispatch(
        kernel,
        LINEAR_GRAPH,
        episode_id,
        capability_iri=SET_CAPABILITY,
        payload={"key": "counter", "value": 5},
        authority_ref=AUTHORITY,
    )

    assert result.accepted is True
    assert result.effect == {
        "before": {"counter": 1},
        "after": {"counter": 5},
        "capability": SET_CAPABILITY,
    }


@pytest.mark.asyncio
async def test_a_call_not_licensed_by_the_graph_is_refused_before_kernel_act():
    """Requesting increment before set (the graph's only licensed START
    transition) must raise DispatchRefusal WITHOUT ever reaching kernel.act
    -- proven by observing no receipt for it exists afterward."""
    kernel = GymAct(authority_resolver=AllowListAuthorityResolver({AUTHORITY}))
    provider = MemoryProvider()
    episode_id = await _materialized_episode(kernel, provider)

    with pytest.raises(DispatchRefusal, match="NOT_LICENSED"):
        await dispatch(
            kernel,
            LINEAR_GRAPH,
            episode_id,
            capability_iri=INCREMENT_CAPABILITY,
            payload={"key": "counter", "amount": 1},
            authority_ref=AUTHORITY,
        )

    receipts = kernel.episode_receipts(episode_id)
    act_capabilities = [r.capability_ref for r in receipts if r.operation.value == "act"]
    assert INCREMENT_CAPABILITY not in act_capabilities


@pytest.mark.asyncio
async def test_a_graph_licensed_call_still_gets_refused_by_authority():
    """The core MCPValidity != DOAuthority proof: the graph licenses `set`
    as the real START transition, but a real DenyAuthorityResolver (no
    authority ever admitted) refuses it anyway -- graph-licensing never
    substitutes for the unchanged authority gate."""
    kernel = GymAct(authority_resolver=DenyAuthorityResolver())
    provider = MemoryProvider()
    episode_id = await _materialized_episode(kernel, provider)

    result = await dispatch(
        kernel,
        LINEAR_GRAPH,
        episode_id,
        capability_iri=SET_CAPABILITY,
        payload={"key": "counter", "value": 5},
        authority_ref=AUTHORITY,
    )

    assert result.accepted is False
    assert result.receipt.reason == "AUTHORITY_NOT_ADMITTED"


@pytest.mark.asyncio
async def test_a_two_step_licensed_sequence_both_succeed_in_order():
    """set then increment, both graph-licensed at their respective points,
    both real kernel.act() calls succeed -- proving licensed_next correctly
    advances as the real receipt history grows."""
    kernel = GymAct(authority_resolver=AllowListAuthorityResolver({AUTHORITY}))
    provider = MemoryProvider()
    episode_id = await _materialized_episode(kernel, provider)

    first = await dispatch(
        kernel,
        LINEAR_GRAPH,
        episode_id,
        capability_iri=SET_CAPABILITY,
        payload={"key": "counter", "value": 10},
        authority_ref=AUTHORITY,
    )
    second = await dispatch(
        kernel,
        LINEAR_GRAPH,
        episode_id,
        capability_iri=INCREMENT_CAPABILITY,
        payload={"key": "counter", "amount": 1},
        authority_ref=AUTHORITY,
    )

    assert first.accepted is True
    assert second.accepted is True
    assert second.effect == {
        "before": {"counter": 10},
        "after": {"counter": 11},
        "capability": INCREMENT_CAPABILITY,
    }
