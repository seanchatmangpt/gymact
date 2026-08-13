"""Chicago-style: a real GymAct episode driven against CUBE's own
container-provisioned `toy_benchmark` example, through a real local Docker
daemon (colima) -- not counter-cube's pure in-memory task.

This closes the two gaps named earlier this session against `test_cube_counter.py`
(counter-cube): (1) `materialize()` here genuinely does something nontrivial
(provisions a real container, CUBE's own `Task.reset()` runs a real
`container.exec("echo infra-ready")` probe inside it), and (2) this task
variant (`count-to-3-with-decrement`) exposes a richer capability set
(increment + decrement + get_value) than counter-cube's default.

Per `gymact.standing.require_standing`, the real thing is the default: if
either the optional `cube`/`docker` extras aren't installed or no Docker
daemon is actually reachable, this module now FAILS unless the run
explicitly sets `GYMACT_ALLOW_DEGRADED_STANDINGS` to include
"LOCAL_GYM:cube-container-counter" (or "*") -- a skip here is something a
run must opt into, never something it silently gets. Matches
`test_cube_counter.py`'s and `test_ggen_legacy_gym.py`'s contract; this
module previously used a plain `pytest.importorskip`/`pytest.mark.skipif`
pair that degraded silently by default, inconsistent with its siblings.
"""

from __future__ import annotations

import importlib.util
import shutil
import subprocess

from gymact.standing import require_standing

try:
    import docker
except ImportError:
    docker = None  # type: ignore[assignment]


def _docker_daemon_reachable() -> bool:
    # Reachability is checked via a real `docker info` subprocess, not
    # `docker.from_env().ping()`, because docker-py's own HTTP client opens
    # its socket eagerly inside `from_env()` (fetching the server API
    # version before `ping()` is ever called) and leaves it unclosed when
    # the daemon refuses the connection -- there is no client object to
    # call `.close()` on in that failure path, since the constructor itself
    # raised before returning one. That leaked socket surfaces later, at an
    # unrelated test's setup, as a `PytestUnraisableExceptionWarning` (seen
    # here failing `test_unknown_action_is_structurally_valid` and
    # `test_default_verifier_catches_a_dishonest_providers_false_success_claim`
    # in a full-suite run). A subprocess owns and cleans up its own socket
    # on exit regardless of connection outcome, so this cannot leak into
    # this process's garbage collector. Same pattern already used by
    # `test_swegym_live.py::_docker_available`.
    if shutil.which("docker") is None:
        return False
    try:
        result = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            text=True,
            timeout=10.0,
            check=False,
        )
        return result.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


require_standing(
    "LOCAL_GYM:cube-container-counter",
    available=importlib.util.find_spec("counter_cube") is not None
    and docker is not None
    and _docker_daemon_reachable(),
    reason="optional 'cube'/'docker' extras not installed, or no reachable Docker daemon "
    "(uv sync --extra cube --all-extras; start colima: `colima start`)",
)

from gymact import AllowListAuthorityResolver, GymAct, MaterializationIntent  # noqa: E402
from gymact.gyms.cube_container_counter import CubeContainerCounterProvider  # noqa: E402
from gymact.models import ActuationIntent, Operation, Standing  # noqa: E402
from gymact.ocel import receipts_to_ocel, validate_ocel_log  # noqa: E402
from gymact.process import ConformanceChecker  # noqa: E402

INCREMENT = "urn:gymact:cube-container-counter:capability:increment"
DECREMENT = "urn:gymact:cube-container-counter:capability:decrement"
GET_VALUE = "urn:gymact:cube-container-counter:capability:get_value"
# cube_container_counter.py's requires_authority now defaults to True (a real
# DO capability against a real Docker container must not run unauthorized) --
# every test below explicitly admits AUTHORITY, matching test_cube_counter.py.
AUTHORITY = "urn:test:cube-container-counter-authority"


def _authorized_gym() -> GymAct:
    gym = GymAct(authority_resolver=AllowListAuthorityResolver({AUTHORITY}))
    gym.register_provider(CubeContainerCounterProvider())
    return gym


async def _run_real_container_episode() -> list:
    gym = _authorized_gym()
    receipts = []

    materialization = await gym.materialize(
        MaterializationIntent(provider="cube-container-counter", config={})
    )
    assert materialization.accepted is True
    receipts.append(materialization.receipt)
    episode_id = materialization.episode.episode_id

    assert materialization.observation.state["containerized"] is True

    for _ in range(3):
        result = await gym.act(
            ActuationIntent(episode_id=episode_id, capability=INCREMENT, authority_ref=AUTHORITY)
        )
        assert result.accepted is True
        receipts.append(result.receipt)

    receipts.append(await gym.teardown(episode_id, authority_ref=AUTHORITY))
    return receipts


async def test_real_container_episode_reaches_target_inside_a_real_docker_container() -> None:
    gym = _authorized_gym()

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
        result = await gym.act(
            ActuationIntent(episode_id=episode_id, capability=INCREMENT, authority_ref=AUTHORITY)
        )
        assert result.accepted is True
        assert result.observation.state["counter"] == expected_counter

    assert (await gym.observe(episode_id)).state["solved"] is True

    v = await gym.verify(episode_id, {"counter": 3, "solved": True})
    assert v.passed is True

    receipt = await gym.teardown(episode_id, authority_ref=AUTHORITY)
    assert receipt.standing == Standing.ALIVE


async def test_decrement_capability_is_real_and_actually_changes_container_state() -> None:
    gym = _authorized_gym()
    m = await gym.materialize(MaterializationIntent(provider="cube-container-counter", config={}))
    episode_id = m.episode.episode_id

    await gym.act(
        ActuationIntent(episode_id=episode_id, capability=INCREMENT, authority_ref=AUTHORITY)
    )
    await gym.act(
        ActuationIntent(episode_id=episode_id, capability=INCREMENT, authority_ref=AUTHORITY)
    )
    assert (await gym.observe(episode_id)).state["counter"] == 2

    result = await gym.act(
        ActuationIntent(episode_id=episode_id, capability=DECREMENT, authority_ref=AUTHORITY)
    )
    assert result.accepted is True
    assert result.observation.state["counter"] == 1

    await gym.teardown(episode_id, authority_ref=AUTHORITY)


async def test_checkpoint_restore_round_trips_the_real_container_state() -> None:
    """Mirrors test_ggen_legacy_gym.py's checkpoint/restore round trip, but
    against real container-backed counter state -- `checkpoint`/`restore`
    existed on this provider before this session but had zero test
    coverage."""
    gym = _authorized_gym()

    materialization = await gym.materialize(
        MaterializationIntent(provider="cube-container-counter", config={})
    )
    episode_id = materialization.episode.episode_id

    await gym.act(
        ActuationIntent(episode_id=episode_id, capability=INCREMENT, authority_ref=AUTHORITY)
    )
    first = await gym.observe(episode_id)
    assert first.state["counter"] == 1

    checkpoint = await gym.checkpoint(episode_id)
    assert checkpoint["counter"] == 1
    assert len(checkpoint["history"]) == 1

    await gym.act(
        ActuationIntent(episode_id=episode_id, capability=INCREMENT, authority_ref=AUTHORITY)
    )
    await gym.act(
        ActuationIntent(episode_id=episode_id, capability=INCREMENT, authority_ref=AUTHORITY)
    )
    assert (await gym.observe(episode_id)).state["counter"] == 3

    restored = await gym.restore(episode_id, checkpoint, authority_ref=AUTHORITY)
    assert restored.standing == Standing.ALIVE

    observed_after_restore = await gym.observe(episode_id)
    assert observed_after_restore.state == first.state

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
