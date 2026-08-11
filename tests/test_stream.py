from __future__ import annotations

import pytest

from gymact import ActuationIntent, AllowListAuthorityResolver, GymAct, MemoryProvider
from gymact.surfaces.faststream import dispatch_stream_command

SET_CAPABILITY = "urn:gymact:memory:capability:set"
AUTHORITY = "urn:test:authority"


@pytest.mark.asyncio
async def test_broker_neutral_stream_dispatch_covers_core_lifecycle() -> None:
    runtime = GymAct(authority_resolver=AllowListAuthorityResolver({AUTHORITY}))
    runtime.register_provider(MemoryProvider())

    discovered = await dispatch_stream_command(runtime, {"operation": "discover"})
    assert discovered == {"operation": "discover", "providers": ["memory"]}

    created = await dispatch_stream_command(
        runtime,
        {
            "operation": "create_episode",
            "provider": "memory",
            "config": {"initial": {"value": 1}},
            "idempotency_key": "stream-materialize",
        },
    )
    assert created["result"]["accepted"] is True
    episode_id = created["result"]["episode"]["episode_id"]

    capabilities = await dispatch_stream_command(
        runtime, {"operation": "capabilities", "episode_id": episode_id}
    )
    assert SET_CAPABILITY in {item["iri"] for item in capabilities["result"]}

    observed = await dispatch_stream_command(
        runtime, {"operation": "observe", "episode_id": episode_id}
    )
    assert observed["result"]["state"] == {"value": 1}

    intent = ActuationIntent(
        episode_id=episode_id,
        capability=SET_CAPABILITY,
        payload={"key": "value", "value": 2},
        idempotency_key="stream-set",
        authority_ref=AUTHORITY,
    )
    actuated = await dispatch_stream_command(
        runtime,
        {"operation": "act", "intent": intent.model_dump(mode="json")},
    )
    assert actuated["result"]["accepted"] is True

    verified = await dispatch_stream_command(
        runtime,
        {"operation": "verify", "episode_id": episode_id, "expected": {"value": 2}},
    )
    assert verified["result"]["passed"] is True

    checkpointed = await dispatch_stream_command(
        runtime, {"operation": "checkpoint", "episode_id": episode_id}
    )
    checkpoint = checkpointed["result"]["checkpoint"]

    await dispatch_stream_command(
        runtime,
        {
            "operation": "act",
            "intent": ActuationIntent(
                episode_id=episode_id,
                capability=SET_CAPABILITY,
                payload={"key": "value", "value": 3},
                idempotency_key="stream-set-again",
                authority_ref=AUTHORITY,
            ).model_dump(mode="json"),
        },
    )
    restored = await dispatch_stream_command(
        runtime,
        {
            "operation": "restore",
            "episode_id": episode_id,
            "checkpoint": checkpoint,
            "authority_ref": AUTHORITY,
        },
    )
    assert restored["result"]["standing"] == "ALIVE"
    assert (await runtime.observe(episode_id)).state == {"value": 2}

    torn_down = await dispatch_stream_command(
        runtime,
        {"operation": "teardown", "episode_id": episode_id, "authority_ref": AUTHORITY},
    )
    assert torn_down["result"]["standing"] == "ALIVE"

    with pytest.raises(ValueError, match="unsupported stream operation"):
        await dispatch_stream_command(runtime, {"operation": "unknown"})
