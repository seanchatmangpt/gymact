"""EXP-GYM-001: deterministic real-simulator rollback falsifiers.

These tests use the installed real CartPole-v1 environment. No mocks or shadow
simulator are admitted: the decisive test compares the transition *after* a
restore with the transition previously observed from the same checkpoint.
"""

from __future__ import annotations

from copy import deepcopy

import pytest

from gymact import AllowListAuthorityResolver, GymAct, MaterializationIntent
from gymact.gyms.gymnasium_env import GYMNASIUM_CAPABILITIES, GymnasiumEnvironment, GymnasiumProvider
from gymact.models import ActuationIntent, Standing

STEP = next(capability for capability in GYMNASIUM_CAPABILITIES if capability.binding == "step")
STEP_REF = STEP.iri
AUTHORITY = "urn:test:gymnasium-replay-authority"


async def _step(environment: GymnasiumEnvironment, action: int) -> dict:
    result = await environment.actuate(STEP, {"action": action})
    return result["after"]


async def test_restore_replays_real_dynamics_not_only_visible_bookkeeping() -> None:
    """Falsifier: same checkpoint + same next action must give same transition."""
    environment = GymnasiumEnvironment(env_id="CartPole-v1", seed=17)
    try:
        await _step(environment, 0)
        await _step(environment, 1)
        checkpoint = await environment.checkpoint()

        expected_next = await _step(environment, 0)
        await _step(environment, 1)  # move real physics farther away

        await environment.restore(checkpoint)
        assert await environment.observe() == checkpoint["state"]
        replayed_next = await _step(environment, 0)

        assert replayed_next == expected_next
    finally:
        await environment.teardown()


async def test_same_seed_and_actions_replay_identically_across_fresh_environments() -> None:
    """Deterministic replay/regeneration court over two real simulator instances."""
    first = GymnasiumEnvironment(env_id="CartPole-v1", seed=23)
    second = GymnasiumEnvironment(env_id="CartPole-v1", seed=23)
    try:
        for action in (0, 1, 1, 0):
            first_state = await _step(first, action)
            second_state = await _step(second, action)
            assert second_state == first_state
        assert await first.checkpoint() != await second.checkpoint()
        # Environment identity differs, but replay-relevant evidence does not.
        first_checkpoint = await first.checkpoint()
        second_checkpoint = await second.checkpoint()
        for key in ("version", "seed", "actions", "state"):
            assert second_checkpoint[key] == first_checkpoint[key]
    finally:
        await first.teardown()
        await second.teardown()


async def test_tampered_expected_state_is_explicitly_falsified() -> None:
    environment = GymnasiumEnvironment(env_id="CartPole-v1", seed=31)
    try:
        await _step(environment, 1)
        checkpoint = await environment.checkpoint()
        tampered = deepcopy(checkpoint)
        tampered["state"]["reward"] = 999.0

        with pytest.raises(RuntimeError, match="GYMNASIUM_REPLAY_RESTORE_DIVERGED"):
            await environment.restore(tampered)
    finally:
        await environment.teardown()


async def test_invalid_checkpoint_is_refused_before_simulator_mutation() -> None:
    environment = GymnasiumEnvironment(env_id="CartPole-v1", seed=41)
    try:
        await _step(environment, 0)
        before = await environment.observe()
        invalid = await environment.checkpoint()
        invalid["actions"].append(99)

        with pytest.raises(ValueError, match="GYMNASIUM_CHECKPOINT_ACTION_INVALID"):
            await environment.restore(invalid)

        assert await environment.observe() == before
    finally:
        await environment.teardown()


async def test_kernel_checkpoint_restore_receipts_real_replay() -> None:
    """Integration: GymAct restore must return ALIVE only after real replay succeeds."""
    gym = GymAct(authority_resolver=AllowListAuthorityResolver({AUTHORITY}))
    gym.register_provider(GymnasiumProvider())
    materialized = await gym.materialize(
        MaterializationIntent(
            provider="gymnasium",
            config={"env_id": "CartPole-v1", "seed": 53},
        )
    )
    assert materialized.accepted is True
    assert materialized.episode is not None
    episode_id = materialized.episode.episode_id

    for action in (0, 1):
        result = await gym.act(
            ActuationIntent(
                episode_id=episode_id,
                capability=STEP_REF,
                payload={"action": action},
                authority_ref=AUTHORITY,
            )
        )
        assert result.accepted is True

    checkpoint = await gym.checkpoint(episode_id)
    expected_from_checkpoint = await gym.act(
        ActuationIntent(
            episode_id=episode_id,
            capability=STEP_REF,
            payload={"action": 0},
            authority_ref=AUTHORITY,
        )
    )
    assert expected_from_checkpoint.accepted is True
    expected_state = (await gym.observe(episode_id)).state

    restore_receipt = await gym.restore(episode_id, checkpoint, authority_ref=AUTHORITY)
    assert restore_receipt.standing == Standing.ALIVE
    restored_state = (await gym.observe(episode_id)).state
    assert restored_state == checkpoint["state"]

    replay = await gym.act(
        ActuationIntent(
            episode_id=episode_id,
            capability=STEP_REF,
            payload={"action": 0},
            authority_ref=AUTHORITY,
        )
    )
    assert replay.accepted is True
    assert (await gym.observe(episode_id)).state == expected_state

    teardown = await gym.teardown(episode_id, authority_ref=AUTHORITY)
    assert teardown.standing == Standing.ALIVE
