from __future__ import annotations

from dataclasses import replace

import pytest

from gymact.gyms.cloud_fidelity import compare_cloud_traces, replay_cloud_trace
from gymact.gyms.cloudsim.capabilities import CAPABILITY_BY_BINDING
from gymact.gyms.cloudsim.provider import CloudSimProvider


CREATE = {
    "service": "compute",
    "operation": "CreateInstance",
    "effect": "CREATE",
    "scope": "prod",
    "region": "us-east",
    "resource_type": "instance",
    "name": "web",
    "properties": {"size": "small"},
}


async def _world():
    return await CloudSimProvider(requires_authority=False).materialize(
        scenario="cloud-fidelity-runtime",
        config={"requires_authority": False},
    )


@pytest.mark.asyncio
async def test_independent_worlds_emit_equivalent_receipted_public_traces() -> None:
    capability = CAPABILITY_BY_BINDING["aws_cloudsim_apply"]
    left = await _world()
    right = await _world()

    await left.actuate_traced(surface="aws-cli", capability=capability, payload=CREATE)
    await right.actuate_traced(surface="aws-cli", capability=capability, payload=CREATE)

    left_trace = left.trace()
    right_trace = right.trace()
    result = compare_cloud_traces(left_trace, right_trace)

    assert result.equivalent is True
    assert result.compared_steps == 1
    assert left.trace_receipt() == right.trace_receipt()
    assert replay_cloud_trace(left_trace, left.trace_receipt()) is True

    response = left_trace[0].response
    assert isinstance(response, dict)
    assert "before" not in response
    assert "after" not in response
    assert response["resource"]["id"].startswith("arn:aws:")


@pytest.mark.asyncio
async def test_failed_actuation_is_traced_without_committing_world_change() -> None:
    capability = CAPABILITY_BY_BINDING["aws_cloudsim_apply"]
    world = await _world()

    await world.actuate_traced(surface="aws-cli", capability=capability, payload=CREATE)
    before = await world.observe()

    with pytest.raises(ValueError, match="resource already exists"):
        await world.actuate_traced(surface="aws-cli", capability=capability, payload=CREATE)

    after = await world.observe()
    assert after == before
    assert len(world.trace()) == 2
    assert world.trace()[1].error_code == "ValueError"
    assert replay_cloud_trace(world.trace(), world.trace_receipt()) is True


@pytest.mark.asyncio
async def test_trace_receipt_refuses_tampered_replay() -> None:
    capability = CAPABILITY_BY_BINDING["aws_cloudsim_apply"]
    world = await _world()

    await world.actuate_traced(surface="aws-cli", capability=capability, payload=CREATE)
    receipt = world.trace_receipt()
    original = world.trace()[0]
    tampered = replace(original, operation="azure_cloudsim_apply")

    assert replay_cloud_trace((tampered,), receipt) is False


@pytest.mark.asyncio
async def test_traced_actuation_refuses_unnamed_surface_before_world_change() -> None:
    capability = CAPABILITY_BY_BINDING["aws_cloudsim_apply"]
    world = await _world()
    before = await world.observe()

    with pytest.raises(ValueError, match="surface must be a non-empty string"):
        await world.actuate_traced(surface=" ", capability=capability, payload=CREATE)

    assert await world.observe() == before
    assert world.trace() == ()
