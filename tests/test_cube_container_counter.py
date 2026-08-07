"""Chicago-style: a real GymAct episode driven against CUBE's own
container-provisioned `toy_benchmark` example, through a real local Docker
daemon (colima) -- not counter-cube's pure in-memory task.

This closes the two gaps named earlier this session against `test_cube_counter.py`
(counter-cube): (1) `materialize()` here genuinely does something nontrivial
(provisions a real container, CUBE's own `Task.reset()` runs a real
`container.exec("echo infra-ready")` probe inside it), and (2) this task
variant (`count-to-3-with-decrement`) exposes a richer capability set
(increment + decrement + get_value) than counter-cube's default.

Skips (named, not silent) if either the optional `cube`/`docker` extras
aren't installed or no Docker daemon is actually reachable -- never a fake
container standing in for a real one.
"""

from __future__ import annotations

import pytest

pytest.importorskip("counter_cube")
docker = pytest.importorskip("docker")


def _docker_daemon_reachable() -> bool:
    try:
        return docker.from_env().ping()
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _docker_daemon_reachable(),
    reason="no reachable Docker daemon (start colima: `colima start`)",
)

from gymact import GymAct, MaterializationIntent  # noqa: E402
from gymact.gyms.cube_container_counter import CubeContainerCounterProvider  # noqa: E402
from gymact.models import ActuationIntent, Operation, Standing  # noqa: E402
from gymact.ocel import receipts_to_ocel, validate_ocel_log  # noqa: E402
from gymact.process import ConformanceChecker  # noqa: E402

INCREMENT = "urn:gymact:cube-container-counter:capability:increment"
DECREMENT = "urn:gymact:cube-container-counter:capability:decrement"
GET_VALUE = "urn:gymact:cube-container-counter:capability:get_value"


async def _run_real_container_episode() -> list:
    gym = GymAct()
    gym.register_provider(CubeContainerCounterProvider())
    receipts = []

    materialization = await gym.materialize(
        MaterializationIntent(provider="cube-container-counter", config={})
    )
    assert materialization.accepted is True
    receipts.append(materialization.receipt)
    episode_id = materialization.episode.episode_id

    assert materialization.observation.state["containerized"] is True

    for _ in range(3):
        result = await gym.act(ActuationIntent(episode_id=episode_id, capability=INCREMENT))
        assert result.accepted is True
        receipts.append(result.receipt)

    receipts.append(await gym.teardown(episode_id))
    return receipts


async def test_real_container_episode_reaches_target_inside_a_real_docker_container() -> None:
    gym = GymAct()
    gym.register_provider(CubeContainerCounterProvider())

    materialization = await gym.materialize(
        MaterializationIntent(provider="cube-container-counter", config={})
    )
    assert materialization.accepted is True
    assert materialization.observation.state == {
        "counter": 0,
        "target": 3,
        "reward": 0.0,
        "solved": False,
        "steps": 0,
        "containerized": True,
    }
    episode_id = materialization.episode.episode_id

    for expected_counter in (1, 2, 3):
        result = await gym.act(ActuationIntent(episode_id=episode_id, capability=INCREMENT))
        assert result.accepted is True
        assert result.observation.state["counter"] == expected_counter

    assert (await gym.observe(episode_id)).state["solved"] is True

    v = await gym.verify(episode_id, {"counter": 3, "solved": True})
    assert v.passed is True

    receipt = await gym.teardown(episode_id)
    assert receipt.standing == Standing.ALIVE


async def test_decrement_capability_is_real_and_actually_changes_container_state() -> None:
    gym = GymAct()
    gym.register_provider(CubeContainerCounterProvider())
    m = await gym.materialize(MaterializationIntent(provider="cube-container-counter", config={}))
    episode_id = m.episode.episode_id

    await gym.act(ActuationIntent(episode_id=episode_id, capability=INCREMENT))
    await gym.act(ActuationIntent(episode_id=episode_id, capability=INCREMENT))
    assert (await gym.observe(episode_id)).state["counter"] == 2

    result = await gym.act(ActuationIntent(episode_id=episode_id, capability=DECREMENT))
    assert result.accepted is True
    assert result.observation.state["counter"] == 1

    await gym.teardown(episode_id)


async def test_container_episode_replays_conformant_and_produces_a_valid_ocel_log() -> None:
    receipts = await _run_real_container_episode()
    operations = [r.operation for r in receipts]

    assert operations == [
        Operation.MATERIALIZE,
        Operation.ACT,
        Operation.ACT,
        Operation.ACT,
        Operation.TEARDOWN,
    ]

    result = ConformanceChecker().check(operations)
    assert result.conformant is True

    log = receipts_to_ocel(receipts)
    validate_ocel_log(log)  # real jsonschema.validate against real OCEL 2.0 schema
