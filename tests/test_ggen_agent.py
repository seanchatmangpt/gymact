from __future__ import annotations

import asyncio

import anyio

from gymact.ggen_agent import (
    CallableGgenManufacturer,
    GgenAgentRuntime,
    GgenAgentSpec,
    manufacture_ggen_agent_space,
)
from gymact.models import Standing


def _spec(*, max_wip: int = 1) -> GgenAgentSpec:
    return GgenAgentSpec(
        agent_id="architect",
        role_ref="urn:test:role:architect",
        planner_ref="urn:test:planner:deterministic",
        objective_ref="urn:test:objective:flow",
        observation_projection_ref="urn:test:projection:observation",
        action_projection_ref="urn:test:projection:action",
        pack_ref="urn:test:pack:ggen",
        observation_keys=("state",),
        output_keys=("artifact",),
        max_wip=max_wip,
    )


async def test_deterministic_agent_has_zero_llm_calls() -> None:
    def manufacture(*, spec, observation, inputs):
        del spec
        return {"artifact": f"{observation['state']}:{inputs['kind']}"}

    runtime = GgenAgentRuntime(
        (_spec(),),
        CallableGgenManufacturer({"architect": manufacture}),
    )

    result = await runtime.invoke(
        "architect",
        observation={"state": "admitted", "ignored": "not-projected"},
        inputs={"kind": "architecture"},
    )

    assert result.standing is Standing.ALIVE
    assert result.output == {"artifact": "admitted:architecture"}
    assert result.llm_calls == 0
    assert runtime.wip() == {"architect": 0}


async def test_wip_limit_refuses_instead_of_queuing() -> None:
    started = anyio.Event()
    release = anyio.Event()

    async def manufacture(*, spec, observation, inputs):
        del spec, observation, inputs
        started.set()
        await release.wait()
        return {"artifact": "done"}

    runtime = GgenAgentRuntime(
        (_spec(max_wip=1),),
        CallableGgenManufacturer({"architect": manufacture}),
    )

    first = asyncio.create_task(
        runtime.invoke("architect", observation={"state": "ready"})
    )
    await started.wait()

    second = await runtime.invoke("architect", observation={"state": "ready"})
    assert second.standing is Standing.REFUSED
    assert second.reason == "LITTLES_LAW_WIP_LIMIT"
    assert second.llm_calls == 0

    release.set()
    completed = await first
    assert completed.standing is Standing.ALIVE
    assert runtime.wip() == {"architect": 0}


def test_dfcm_agent_space_preserves_cross_product_without_selection() -> None:
    space = manufacture_ggen_agent_space(
        roles=("architect", "tester"),
        planners=("p1", "p2"),
        objectives=("flow", "quality"),
        observation_projections=("full",),
        action_projections=("artifact",),
        packs=("pack",),
    )

    assert space.total_cardinality == 8
    assert len(space.combinations) == 8
    assert space.truncated is False
