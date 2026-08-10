"""Chicago-style: a real GymAct episode driven against a real, standard
`gymnasium` environment (`CartPole-v1`) -- no vendored agentgym, no mocked
`gymnasium.Env`, no subprocess.

`GymAct.materialize` really instantiates `GymnasiumEnvironment`, which really
wraps a real `gymnasium.make("CartPole-v1")` object; every `act()` call below
really calls the real env's `step()`.
"""

from __future__ import annotations

from pathlib import Path

from gymact import AllowListAuthorityResolver, GymAct, MaterializationIntent
from gymact.gyms.gymnasium_env import GymnasiumProvider
from gymact.models import ActuationIntent, Operation, Standing
from gymact.ocel import validate_ocel_log, write_ocel_log
from gymact.process import ConformanceChecker

STEP_CAPABILITY = "urn:gymact:gymnasium:capability:step"
RESET_CAPABILITY = "urn:gymact:gymnasium:capability:reset"
SAMPLE_ACTION_CAPABILITY = "urn:gymact:gymnasium:capability:sample_action"
# gymnasium_env.py's requires_authority now defaults to True (a real DO
# capability stepping a real env must not run unauthorized) -- every test
# below explicitly admits AUTHORITY, matching test_cube_counter.py's pattern.
AUTHORITY = "urn:test:gymnasium-authority"


def _authorized_gym() -> GymAct:
    gym = GymAct(authority_resolver=AllowListAuthorityResolver({AUTHORITY}))
    gym.register_provider(GymnasiumProvider())
    return gym


async def _run_real_cartpole_episode(gym: GymAct) -> tuple[list, list[Operation]]:
    receipts = []

    materialization = await gym.materialize(
        MaterializationIntent(provider="gymnasium", config={"env_id": "CartPole-v1"})
    )
    assert materialization.accepted is True
    receipts.append(materialization.receipt)
    episode_id = materialization.episode.episode_id

    observation = await gym.observe(episode_id)
    assert observation.state["env_id"] == "CartPole-v1"
    assert isinstance(observation.state["observation"], list)
    assert len(observation.state["observation"]) == 4  # CartPole's real 4-float state
    assert observation.state["reward"] is None
    assert observation.state["terminated"] is False

    # CartPole's real discrete action space is {0, 1}; drive a few real steps
    # (0 = push left, 1 = push right) and assert on the real returned state,
    # never a re-derived shadow value.
    for action in (0, 1, 0, 1, 0):
        result = await gym.act(
            ActuationIntent(
                episode_id=episode_id,
                capability=STEP_CAPABILITY,
                payload={"action": action},
                authority_ref=AUTHORITY,
            )
        )
        assert result.accepted is True
        receipts.append(result.receipt)

    after_steps = await gym.observe(episode_id)
    assert after_steps.state["reward"] is not None
    assert after_steps.state["observation"] != observation.state["observation"]

    teardown_receipt = await gym.teardown(episode_id, authority_ref=AUTHORITY)
    receipts.append(teardown_receipt)

    return receipts, [r.operation for r in receipts]


async def test_real_cartpole_episode_steps_and_is_receipted() -> None:
    gym_instance = _authorized_gym()

    receipts, operations = await _run_real_cartpole_episode(gym_instance)

    assert operations == [
        Operation.MATERIALIZE,
        Operation.ACT,
        Operation.ACT,
        Operation.ACT,
        Operation.ACT,
        Operation.ACT,
        Operation.TEARDOWN,
    ]
    assert all(r.standing == "ALIVE" for r in receipts)


async def test_real_cartpole_episode_replays_conformant_against_declared_lifecycle() -> None:
    gym_instance = _authorized_gym()

    _receipts, operations = await _run_real_cartpole_episode(gym_instance)

    result = ConformanceChecker().check(operations)

    assert result.conformant is True
    assert result.deviations == []


async def test_illegal_action_is_refused_and_does_not_change_real_state() -> None:
    gym_instance = _authorized_gym()
    materialized = await gym_instance.materialize(
        MaterializationIntent(provider="gymnasium", config={"env_id": "CartPole-v1"})
    )
    episode_id = materialized.episode.episode_id
    before = await gym_instance.observe(episode_id)

    result = await gym_instance.act(
        ActuationIntent(
            episode_id=episode_id,
            capability=STEP_CAPABILITY,
            # CartPole's real discrete(2) action space only admits {0, 1}.
            payload={"action": 99},
            authority_ref=AUTHORITY,
        )
    )

    assert result.accepted is False
    after = await gym_instance.observe(episode_id)
    assert after.state == before.state

    await gym_instance.teardown(episode_id, authority_ref=AUTHORITY)


async def test_sample_action_capability_is_read_and_refused_via_act() -> None:
    # sample_action is declared Consequence.READ (it queries action_space.sample(),
    # it does not step the real env). Per gymact's consequence law, a READ
    # capability can never be smuggled through act() -- the kernel refuses it
    # with READ_CAPABILITY_IS_NOT_ACTUATION, matching test_core.py's
    # test_read_capability_cannot_be_smuggled_through_actuation.
    gym_instance = _authorized_gym()
    materialized = await gym_instance.materialize(
        MaterializationIntent(provider="gymnasium", config={"env_id": "CartPole-v1"})
    )
    episode_id = materialized.episode.episode_id

    result = await gym_instance.act(
        ActuationIntent(
            episode_id=episode_id, capability=SAMPLE_ACTION_CAPABILITY, authority_ref=AUTHORITY
        )
    )

    assert result.accepted is False
    assert result.standing == Standing.REFUSED
    assert result.receipt.reason == "READ_CAPABILITY_IS_NOT_ACTUATION"
    observed = await gym_instance.observe(episode_id)
    assert observed.state["reward"] is None

    await gym_instance.teardown(episode_id, authority_ref=AUTHORITY)


async def test_reset_capability_really_restarts_the_real_episode() -> None:
    gym_instance = _authorized_gym()
    materialized = await gym_instance.materialize(
        MaterializationIntent(provider="gymnasium", config={"env_id": "CartPole-v1"})
    )
    episode_id = materialized.episode.episode_id

    await gym_instance.act(
        ActuationIntent(
            episode_id=episode_id,
            capability=STEP_CAPABILITY,
            payload={"action": 1},
            authority_ref=AUTHORITY,
        )
    )
    stepped = await gym_instance.observe(episode_id)
    assert stepped.state["reward"] is not None

    reset_result = await gym_instance.act(
        ActuationIntent(episode_id=episode_id, capability=RESET_CAPABILITY, authority_ref=AUTHORITY)
    )
    assert reset_result.accepted is True

    after_reset = await gym_instance.observe(episode_id)
    assert after_reset.state["reward"] is None
    assert after_reset.state["terminated"] is False

    await gym_instance.teardown(episode_id, authority_ref=AUTHORITY)


async def test_verify_matches_real_observed_cartpole_state() -> None:
    gym_instance = _authorized_gym()
    materialized = await gym_instance.materialize(
        MaterializationIntent(provider="gymnasium", config={"env_id": "CartPole-v1"})
    )
    episode_id = materialized.episode.episode_id

    verification = await gym_instance.verify(episode_id, {"env_id": "CartPole-v1"})
    assert verification.passed is True

    bad_verification = await gym_instance.verify(episode_id, {"env_id": "not-cartpole"})
    assert bad_verification.passed is False

    await gym_instance.teardown(episode_id, authority_ref=AUTHORITY)


async def test_real_cartpole_episode_ocel_log_is_written_and_schema_valid(tmp_path: Path) -> None:
    gym_instance = _authorized_gym()

    receipts, _operations = await _run_real_cartpole_episode(gym_instance)

    log_path = tmp_path / "gymnasium-episode.ocel.json"
    log, digest = write_ocel_log(log_path, receipts)

    # write_ocel_log already validates before persisting; re-validate the
    # bytes actually written to disk (independent, not trusting in-memory state).
    validate_ocel_log(log)
    import hashlib
    import json

    written = log_path.read_text()
    assert hashlib.sha256(written.encode()).hexdigest() == digest
    reloaded = json.loads(written)
    validate_ocel_log(reloaded)

    event_types = {et["name"] for et in log["eventTypes"]}
    assert event_types == {"materialize", "act", "teardown"}
    assert all(r.standing == Standing.ALIVE for r in receipts)
