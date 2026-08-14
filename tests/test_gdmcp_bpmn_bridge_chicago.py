"""Chicago-style tests for `gymact.gdmcp_bpmn_bridge`. Real GymAct kernel,
real MemoryProvider, real SpiffWorkflow parse+run, real generated BPMN
XML -- no mocks. Uses a real, hand-built `CompiledGdmcpProgram`-shaped
object against `MemoryProvider` (portable, no SREGym/k8s dependency), not
`gdmcp.compile_sregym_solution` directly, to keep this test suite runnable
everywhere -- `gdmcp.py` itself is exercised separately by its own real
import check.
"""

from __future__ import annotations

import pytest

from gymact.authority import AllowListAuthorityResolver, DenyAuthorityResolver
from gymact.gdmcp import CompiledGdmcpProgram
from gymact.gdmcp_bpmn_bridge import (
    BpmnReplayRefusal,
    compile_program_to_bpmn,
    replay_compiled_program_via_bpmn,
)
from gymact.kernel import GymAct
from gymact.models import ActuationIntent, MaterializationIntent
from gymact.providers import MemoryProvider

AUTHORITY = "urn:gymact:test:gdmcp-bpmn-bridge"
SET_CAPABILITY = "urn:gymact:memory:capability:set"
INCREMENT_CAPABILITY = "urn:gymact:memory:capability:increment"


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


def _real_program(episode_id: str, authority_ref: str | None) -> CompiledGdmcpProgram:
    intents = (
        ActuationIntent(
            episode_id=episode_id,
            capability=SET_CAPABILITY,
            payload={"key": "counter", "value": 10},
            authority_ref=authority_ref,
        ),
        ActuationIntent(
            episode_id=episode_id,
            capability=INCREMENT_CAPABILITY,
            payload={"key": "counter", "amount": 5},
            authority_ref=authority_ref,
        ),
    )
    return CompiledGdmcpProgram(
        program_digest="sha256:" + "ab" * 32,
        problem_id="memory-set-then-increment",
        upstream_revision="n/a",
        intents=intents,
    )


def test_compile_program_to_bpmn_carries_only_integer_indices_never_real_values():
    """The generated XML must never contain the real capability IRI,
    payload values, or authority_ref -- only integer step indices."""
    program = _real_program("urn:gymact:episode:fixture", AUTHORITY)
    xml = compile_program_to_bpmn(program)

    assert SET_CAPABILITY not in xml
    assert INCREMENT_CAPABILITY not in xml
    assert AUTHORITY not in xml
    assert '<spiffworkflow:serviceTaskOperator id="0"' in xml
    assert '<spiffworkflow:serviceTaskOperator id="1"' in xml


@pytest.mark.asyncio
async def test_real_replay_dispatches_both_intents_in_real_bpmn_determined_order():
    kernel = GymAct(authority_resolver=AllowListAuthorityResolver({AUTHORITY}))
    provider = MemoryProvider()
    episode_id = await _materialized_episode(kernel, provider)
    program = _real_program(episode_id, AUTHORITY)

    results = await replay_compiled_program_via_bpmn(kernel, program)

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
async def test_bpmn_scheduling_never_bypasses_authority_admission():
    """MCPValidity != DOAuthority, checked directly: BPMN determines a real
    fire order, but a real DenyAuthorityResolver still refuses the actual
    kernel.act() call -- the bridge never grants authority itself."""
    kernel = GymAct(authority_resolver=DenyAuthorityResolver())
    provider = MemoryProvider()
    episode_id = await _materialized_episode_deny(kernel, provider)
    program = _real_program(episode_id, AUTHORITY)

    results = await replay_compiled_program_via_bpmn(kernel, program)

    assert results[0].accepted is False
    assert results[0].receipt.reason == "AUTHORITY_NOT_ADMITTED"


async def _materialized_episode_deny(kernel: GymAct, provider: MemoryProvider) -> str:
    """Materialize with requires_authority=True and no authority_ref
    supplied at materialize time -- so the episode itself comes to real
    existence (materialize does not require authority by default here),
    but its real MemoryEnvironment.requires_authority=True, which is what
    makes the later real kernel.act() call actually consult the resolver
    instead of short-circuiting (real behavior:
    GymAct._authority_decision's required=False path never even calls the
    resolver -- confirmed the same way this session's other equivalent
    refusal tests already do)."""
    kernel.register_provider(provider)
    result = await kernel.materialize(
        MaterializationIntent(provider=provider.name, config={"requires_authority": True})
    )
    assert result.accepted, result.receipt.reason
    assert result.episode is not None
    return result.episode.episode_id


def test_empty_program_is_refused_before_any_real_bpmn_parse():
    empty_program = CompiledGdmcpProgram(
        program_digest="sha256:" + "00" * 32,
        problem_id="empty",
        upstream_revision="n/a",
        intents=(),
    )
    with pytest.raises(BpmnReplayRefusal, match="EMPTY_PROGRAM"):
        compile_program_to_bpmn(empty_program)
