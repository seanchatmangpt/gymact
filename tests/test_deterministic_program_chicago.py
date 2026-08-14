"""Chicago-style tests for `gymact.deterministic_program`. Real `GymAct`
kernel, real `gymact.providers.MemoryProvider`, real
`AllowListAuthorityResolver` -- no mocks. Reuses
`tests/test_mcp_process_control_chicago.py`'s real "set precedes increment"
graph as the worked example's `ProcessControlGraph`.
"""

from __future__ import annotations

import pytest

from gymact.authority import AllowListAuthorityResolver
from gymact.deterministic_program import (
    DeterministicProgramSpec,
    ProgramNotFound,
    compile_program,
    run_deterministic_program,
)
from gymact.kernel import GymAct
from gymact.mcp_process_control import ProcessControlGraph, ProcessTransition
from gymact.models import MaterializationIntent
from gymact.providers import MemoryProvider

AUTHORITY = "urn:gymact:test:deterministic-program-authority"
SET_CAPABILITY = "urn:gymact:memory:capability:set"
INCREMENT_CAPABILITY = "urn:gymact:memory:capability:increment"

LINEAR_GRAPH = ProcessControlGraph(
    graph_id="urn:gymact:test:deterministic-program:linear-set-then-increment",
    transitions=(
        ProcessTransition(from_capability=None, to_capability=SET_CAPABILITY),
        ProcessTransition(from_capability=SET_CAPABILITY, to_capability=INCREMENT_CAPABILITY),
    ),
)

SET_AND_INCREMENT_SPEC = DeterministicProgramSpec(
    provider_name="memory",
    problem_id="set-then-increment-counter",
    graph=LINEAR_GRAPH,
    step_order=(SET_CAPABILITY, INCREMENT_CAPABILITY),
    # `value`/`amount` are real, fixed numeric literals -- not templated,
    # because `_render` only substitutes into string fields, and
    # MemoryEnvironment.actuate's "increment" binding real-type-checks its
    # current/amount values (raises TypeError on a non-numeric value). Only
    # the string-typed key name is bound, the realistic shape for
    # gdmcp-style bindings (namespace/identifier strings, not arbitrary
    # typed values).
    payload_templates={
        SET_CAPABILITY: {"key": "{{memory_key}}", "value": 10},
        INCREMENT_CAPABILITY: {"key": "{{memory_key}}", "amount": 5},
    },
    required_bindings=frozenset({"memory_key"}),
)

CATALOG: dict[tuple[str, str], DeterministicProgramSpec] = {
    ("memory", "set-then-increment-counter"): SET_AND_INCREMENT_SPEC,
}


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


@pytest.mark.asyncio
async def test_real_program_compiles_and_runs_end_to_end_llm_calls_zero():
    """Real, worked example: compile the catalog entry, render its
    {{placeholder}} templates against real bindings, replay it through
    dispatch() end to end -- no LLM call anywhere in this path."""
    kernel = GymAct(authority_resolver=AllowListAuthorityResolver({AUTHORITY}))
    provider = MemoryProvider()
    episode_id = await _materialized_episode(kernel, provider)

    spec = compile_program(CATALOG, provider_name="memory", problem_id="set-then-increment-counter")
    results = await run_deterministic_program(
        kernel,
        spec,
        episode_id,
        bindings={"memory_key": "counter"},
        authority_ref=AUTHORITY,
    )

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
async def test_unknown_problem_id_refuses_before_any_kernel_call():
    """compile_program must raise ProgramNotFound for an uncatalogued
    (provider_name, problem_id) -- fail-closed, mirroring gdmcp's
    GDMCP_SOLUTION_UNKNOWN, never falling back to an LLM."""
    with pytest.raises(ProgramNotFound, match="UNKNOWN_PROGRAM"):
        compile_program(CATALOG, provider_name="memory", problem_id="never-heard-of-this")


@pytest.mark.asyncio
async def test_missing_required_binding_refuses_before_any_kernel_call():
    """A real refusal, checked before dispatch() is ever called -- proven by
    asserting no receipt exists afterward for either capability."""
    kernel = GymAct(authority_resolver=AllowListAuthorityResolver({AUTHORITY}))
    provider = MemoryProvider()
    episode_id = await _materialized_episode(kernel, provider)

    with pytest.raises(ProgramNotFound, match="MISSING_BINDINGS"):
        await run_deterministic_program(
            kernel,
            SET_AND_INCREMENT_SPEC,
            episode_id,
            bindings={},  # memory_key missing
            authority_ref=AUTHORITY,
        )

    receipts = kernel.episode_receipts(episode_id)
    act_capabilities = [r.capability_ref for r in receipts if r.operation.value == "act"]
    assert act_capabilities == []
