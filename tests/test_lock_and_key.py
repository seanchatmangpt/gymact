"""Chicago-style: real `GymAct` episodes against the real `LockAndKeyProvider`
(`gymact.gyms.lock_and_key`) -- ordered hidden key/lock permutation, with a
dedicated test for the `force_latch` irreversible dead-end trap.

No mocks: real kernel, real environment, real authority resolvers, real
state-based assertions on returned/observed dicts.
"""

from __future__ import annotations

from gymact import AllowListAuthorityResolver, GymAct, MaterializationIntent
from gymact.gyms.lock_and_key import LOCK_AND_KEY_CAPABILITIES, LockAndKeyProvider
from gymact.models import ActuationIntent, Standing

PICK_KEY = "urn:gymact:lock-and-key:capability:pick_key"
DROP_KEY = "urn:gymact:lock-and-key:capability:drop_key"
OPEN_LOCK = "urn:gymact:lock-and-key:capability:open_lock"
FORCE_LATCH = "urn:gymact:lock-and-key:capability:force_latch"
READ_LOCKS = "urn:gymact:lock-and-key:capability:read_locks"
AUTHORITY = "urn:test:lock-and-key-authority"


def _gym() -> GymAct:
    gym = GymAct(authority_resolver=AllowListAuthorityResolver({AUTHORITY}))
    gym.register_provider(LockAndKeyProvider())
    return gym


async def _materialize(gym: GymAct, config: dict) -> str:
    materialization = await gym.materialize(
        MaterializationIntent(provider="lock-and-key", config=config)
    )
    assert materialization.accepted is True, materialization.receipt.reason
    return materialization.episode.episode_id


def test_capability_shapes_match_module_constant() -> None:
    assert len(LOCK_AND_KEY_CAPABILITIES) == 5
    bindings = {c.binding for c in LOCK_AND_KEY_CAPABILITIES}
    assert bindings == {"pick_key", "drop_key", "open_lock", "force_latch", "read_locks"}
    for cap in LOCK_AND_KEY_CAPABILITIES:
        if cap.binding == "read_locks":
            assert cap.consequence.value == "READ"
        else:
            assert cap.consequence.value == "DO"


async def test_materialize_creates_real_episode_with_locked_state() -> None:
    gym = _gym()
    episode_id = await _materialize(gym, {"seed": 1, "depth": 3})

    observation = await gym.observe(episode_id)
    assert observation.state["depth"] == 3
    assert observation.state["locks_open"] == 0
    assert observation.state["solved"] is False
    assert observation.state["holding_key"] is False

    await gym.teardown(episode_id, authority_ref=AUTHORITY)


async def test_full_episode_solves_the_lock_chain_using_the_hidden_permutation() -> None:
    """Drives the real environment to solved=True by discovering the hidden
    permutation through the module's own oracle helper (`required_key()`),
    exactly the intended discovery-agent contract -- no shortcut."""
    gym = _gym()
    episode_id = await _materialize(gym, {"seed": 7, "depth": 3})
    env = gym._episodes[episode_id].environment

    while not env._solved():
        key = env.required_key()
        pick = await gym.act(
            ActuationIntent(
                episode_id=episode_id,
                capability=PICK_KEY,
                payload={"key": key},
                authority_ref=AUTHORITY,
            )
        )
        assert pick.accepted is True, pick.receipt.reason

        opened = await gym.act(
            ActuationIntent(episode_id=episode_id, capability=OPEN_LOCK, authority_ref=AUTHORITY)
        )
        assert opened.accepted is True, opened.receipt.reason
        assert opened.effect["applicable"] is True

    observation = await gym.observe(episode_id)
    assert observation.state["solved"] is True
    assert observation.state["locks_open"] == 3

    verification = await gym.verify(episode_id, {"solved": True})
    assert verification.passed is True

    await gym.teardown(episode_id, authority_ref=AUTHORITY)


async def test_opening_a_lock_without_the_correct_key_is_refused_as_inapplicable() -> None:
    gym = _gym()
    episode_id = await _materialize(gym, {"seed": 3, "depth": 2})
    env = gym._episodes[episode_id].environment
    wrong_key = next(k for k in range(2) if k != env.required_key())

    pick = await gym.act(
        ActuationIntent(
            episode_id=episode_id,
            capability=PICK_KEY,
            payload={"key": wrong_key},
            authority_ref=AUTHORITY,
        )
    )
    assert pick.accepted is True

    opened = await gym.act(
        ActuationIntent(episode_id=episode_id, capability=OPEN_LOCK, authority_ref=AUTHORITY)
    )
    # act() accepts the intent (kernel-level admission), but the environment's
    # own applicability guard reports the precondition failure in the effect.
    assert opened.accepted is True
    assert opened.effect["applicable"] is False
    assert "does not fit" in opened.effect["result_text"]

    observation = await gym.observe(episode_id)
    assert observation.state["locks_open"] == 0

    await gym.teardown(episode_id, authority_ref=AUTHORITY)


async def test_force_latch_is_a_one_shot_irreversible_trap_that_reaches_a_dead_end() -> None:
    """depth=3: forcing the first lock jams the rack forever, leaving 2 locks
    still closed -- `_dead_end()` must report True, and a second force_latch
    must be refused as inapplicable (rack already jammed), not repeatable."""
    gym = _gym()
    episode_id = await _materialize(gym, {"seed": 5, "depth": 3})

    forced = await gym.act(
        ActuationIntent(episode_id=episode_id, capability=FORCE_LATCH, authority_ref=AUTHORITY)
    )
    assert forced.accepted is True
    assert forced.effect["applicable"] is True
    assert forced.effect["after"]["locks_open"] == 1
    assert forced.effect["after"]["rack_jammed"] is True
    assert forced.effect["after"]["dead_end"] is True

    # Picking a key is now refused too -- the rack is jammed.
    pick = await gym.act(
        ActuationIntent(
            episode_id=episode_id,
            capability=PICK_KEY,
            payload={"key": 0},
            authority_ref=AUTHORITY,
        )
    )
    assert pick.accepted is True
    assert pick.effect["applicable"] is False
    assert "jammed" in pick.effect["result_text"]

    # A second force_latch is a one-shot trap, not a repeatable exploit.
    forced_again = await gym.act(
        ActuationIntent(episode_id=episode_id, capability=FORCE_LATCH, authority_ref=AUTHORITY)
    )
    assert forced_again.accepted is True
    assert forced_again.effect["applicable"] is False
    assert "already jammed" in forced_again.effect["result_text"]

    observation = await gym.observe(episode_id)
    assert observation.state["solved"] is False
    assert observation.state["dead_end"] is True

    await gym.teardown(episode_id, authority_ref=AUTHORITY)


async def test_checkpoint_restore_round_trip_recovers_real_progress() -> None:
    gym = _gym()
    episode_id = await _materialize(gym, {"seed": 11, "depth": 2})
    env = gym._episodes[episode_id].environment
    key = env.required_key()

    await gym.act(
        ActuationIntent(
            episode_id=episode_id,
            capability=PICK_KEY,
            payload={"key": key},
            authority_ref=AUTHORITY,
        )
    )
    opened = await gym.act(
        ActuationIntent(episode_id=episode_id, capability=OPEN_LOCK, authority_ref=AUTHORITY)
    )
    assert opened.accepted is True

    checkpoint = await gym.checkpoint(episode_id)
    assert checkpoint["locks_open"] == 1

    # Advance further, then restore back to the checkpointed lock count.
    key2 = env.required_key()
    await gym.act(
        ActuationIntent(
            episode_id=episode_id,
            capability=PICK_KEY,
            payload={"key": key2},
            authority_ref=AUTHORITY,
        )
    )
    await gym.act(
        ActuationIntent(episode_id=episode_id, capability=OPEN_LOCK, authority_ref=AUTHORITY)
    )
    solved_observation = await gym.observe(episode_id)
    assert solved_observation.state["solved"] is True

    await gym.restore(episode_id, checkpoint, authority_ref=AUTHORITY)

    restored = await gym.observe(episode_id)
    assert restored.state["locks_open"] == 1
    assert restored.state["solved"] is False

    await gym.teardown(episode_id, authority_ref=AUTHORITY)


async def test_read_locks_via_observe_never_leaks_hidden_permutation_field() -> None:
    gym = _gym()
    episode_id = await _materialize(gym, {"seed": 2, "depth": 2})

    observation = await gym.observe(episode_id)
    assert "_perm" not in observation.state
    assert "perm" not in observation.state

    read_attempt = await gym.act(
        ActuationIntent(episode_id=episode_id, capability=READ_LOCKS, authority_ref=AUTHORITY)
    )
    assert read_attempt.accepted is False

    await gym.teardown(episode_id, authority_ref=AUTHORITY)


async def test_do_capability_is_refused_without_admitted_authority() -> None:
    """A plain GymAct() defaults to DenyAuthorityResolver -- pick_key must be
    refused when requires_authority=True, not silently authorized."""
    gym = GymAct()
    gym.register_provider(LockAndKeyProvider())
    materialization = await gym.materialize(
        MaterializationIntent(
            provider="lock-and-key",
            config={"seed": 1, "depth": 2, "requires_authority": True},
        )
    )
    assert materialization.accepted is True, materialization.receipt.reason
    episode_id = materialization.episode.episode_id

    result = await gym.act(
        ActuationIntent(
            episode_id=episode_id, capability=PICK_KEY, payload={"key": 0}
        )
    )

    assert result.accepted is False
    assert result.standing is Standing.REFUSED

    await gym.teardown(episode_id)
