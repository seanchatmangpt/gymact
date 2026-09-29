"""An idempotency key reused across episodes must be a typed, receipted REFUSAL.

Consequence law (CLAUDE.md): "Idempotency-key reuse with a different intent is a refusal,
not a replay" and provider failures must not become unreceipted consequential operations.

The kernel caches actuation idempotency per (episode, key) while the evidence ledger
enforces key uniqueness globally by (episode, capability). A key reused from ANOTHER
episode therefore slipped past the kernel, actuated the provider, and only then made the
ledger append raise ValueError: the world changed with no ACT receipt.
"""

from __future__ import annotations

from gymact import AllowListAuthorityResolver, GymAct, MaterializationIntent, MemoryProvider
from gymact.models import ActuationIntent, Operation, Standing

AUTH = "urn:test:idempotency-authority"
SET_CAPABILITY = "urn:gymact:memory:capability:set"


async def _gym_with_episodes(count: int) -> tuple[GymAct, list[str], list[str]]:
    gym = GymAct(authority_resolver=AllowListAuthorityResolver({AUTH}))
    gym.register_provider(MemoryProvider())
    episodes: list[str] = []
    materialize_keys: list[str] = []
    for _ in range(count):
        intent = MaterializationIntent(
            provider="memory",
            config={"initial": {}, "requires_authority": True},
            authority_ref=AUTH,
        )
        materialized = await gym.materialize(intent)
        assert materialized.accepted, materialized.receipt.reason
        episodes.append(materialized.episode.episode_id)
        materialize_keys.append(intent.idempotency_key)
    return gym, episodes, materialize_keys


def _act(episode_id: str, key: str, value: int) -> ActuationIntent:
    return ActuationIntent(
        episode_id=episode_id,
        capability=SET_CAPABILITY,
        payload={"key": "a", "value": value},
        authority_ref=AUTH,
        idempotency_key=key,
    )


async def test_key_reused_from_another_episode_is_a_typed_receipted_refusal() -> None:
    gym, (first, second), _ = await _gym_with_episodes(2)

    original = await gym.act(_act(first, "shared-key", 1))
    assert original.receipt.standing == Standing.ALIVE

    result = await gym.act(_act(second, "shared-key", 1))  # must not raise

    assert result.accepted is False
    assert result.receipt.standing == Standing.REFUSED
    assert result.receipt.reason == "IDEMPOTENCY_KEY_CONFLICT"
    # The refusal is evidence in the requesting episode, and the world did not change.
    acts = [r for r in gym.episode_receipts(second) if r.operation == Operation.ACT]
    assert [(r.standing, r.reason) for r in acts] == [
        (Standing.REFUSED, "IDEMPOTENCY_KEY_CONFLICT")
    ]
    assert (await gym.observe(second)).state == {}
    # The original episode is untouched and the ledger chain still verifies.
    assert (await gym.observe(first)).state == {"a": 1}
    assert gym.ledger.verify() is True


async def test_conflict_refusal_leaves_the_requesting_episode_usable_with_a_fresh_key() -> None:
    gym, (first, second), _ = await _gym_with_episodes(2)
    await gym.act(_act(first, "shared-key", 1))
    assert (await gym.act(_act(second, "shared-key", 1))).accepted is False

    fresh = await gym.act(_act(second, "fresh-key", 5))

    assert fresh.receipt.standing == Standing.ALIVE
    assert (await gym.observe(second)).state == {"a": 5}


async def test_act_key_equal_to_a_materialization_key_is_refused_not_raised() -> None:
    gym, (first, second), materialize_keys = await _gym_with_episodes(2)

    result = await gym.act(_act(second, materialize_keys[0], 1))  # first episode's key

    assert result.accepted is False
    assert result.receipt.reason == "IDEMPOTENCY_KEY_CONFLICT"
    assert (await gym.observe(second)).state == {}
    assert (await gym.observe(first)).state == {}


async def test_legitimate_replay_in_the_same_episode_is_unchanged() -> None:
    gym, (episode, _), _ = await _gym_with_episodes(2)
    first = await gym.act(_act(episode, "replay-key", 1))
    replay = await gym.act(_act(episode, "replay-key", 1))

    assert first.receipt.standing == replay.receipt.standing == Standing.ALIVE
    assert first.receipt.receipt_id == replay.receipt.receipt_id  # replay returns the cached result
    different = await gym.act(_act(episode, "replay-key", 2))
    assert different.receipt.standing == Standing.REFUSED
    assert different.receipt.reason == "IDEMPOTENCY_KEY_CONFLICT"
    assert (await gym.observe(episode)).state == {"a": 1}
