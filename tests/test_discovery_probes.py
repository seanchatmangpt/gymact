from __future__ import annotations

from collections import deque

import pytest

from gymact.discovery import DiscoveryProbeRunner
from gymact.gyms.opaque_procedure import OpaqueProcedureProvider
from gymact.models import Standing
from gymact.ocel import validate_ocel_log
from gymact.runtime import ProductionGymAct

PRIVATE = {
    "subject": "test/held-out",
    "initial_facts": ["start"],
    "goal_facts": ["done"],
    "steps": [
        {
            "id": "finish-human-readable",
            "preconditions": ["middle"],
            "establishes": ["done"],
        },
        {
            "id": "begin-human-readable",
            "preconditions": ["start"],
            "establishes": ["middle"],
        },
    ],
}


async def _discover(runner: DiscoveryProbeRunner) -> tuple[str, ...]:
    initial, actions = await runner.challenge()
    queue = deque([(frozenset(initial), ())])
    seen = {frozenset(initial)}
    while queue:
        _state, prefix = queue.popleft()
        for action in actions:
            evidence = await runner.probe(prefix=prefix, action_id=action)
            if not evidence.accepted:
                assert evidence.standing in {
                    Standing.BLOCKED,
                    Standing.REFUSED,
                    Standing.UNSUPPORTED,
                }
                continue
            after = frozenset(evidence.after_facts)
            candidate = prefix + (action,)
            if "done" in after:
                return candidate
            if after not in seen:
                seen.add(after)
                queue.append((after, candidate))
    raise AssertionError("goal was not discovered")


@pytest.mark.asyncio
async def test_opaque_probe_discovery_is_brce_receipted_and_replayable() -> None:
    runtime = ProductionGymAct(validate_profile=False)
    runtime.register_provider(OpaqueProcedureProvider())
    runner = DiscoveryProbeRunner(
        runtime,
        provider="opaque-procedure",
        subject="test/held-out",
        private_config=PRIVATE,
    )
    initial, actions = await runner.challenge()
    assert initial == ("start",)
    assert len(actions) == 2
    assert all(item.startswith("urn:gymact:opaque:action:") for item in actions)
    assert all("human-readable" not in item for item in actions)
    plan = await _discover(runner)
    assert len(plan) == 2
    replay = await runner.replay(plan=plan)
    assert replay.standing is Standing.ALIVE
    assert replay.goal_reached is True
    assert "done" in replay.final_facts
    assert replay.receipt_ids
    assert validate_ocel_log(replay.ocel_log) is None
