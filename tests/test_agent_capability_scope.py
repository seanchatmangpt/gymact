"""Chicago-style proof of CapabilityScope + principal threading -- real
MemoryProvider episodes, real GymAct kernel, real Receipt state. No test
doubles of any kind are used in this file: see
`.claude/rules/testing-chicago-style.md` and `src/gymact/agent.py`'s
docstring for why this externalization pattern (an injected, kernel-owned
judge/gate, never the provider's or caller's own to decide) is gymact's
established idiom.
"""

from __future__ import annotations

from gymact import (
    ActuationIntent,
    AllowAllCapabilityScope,
    AllowListCapabilityScope,
    GymAct,
    MaterializationIntent,
    MemoryProvider,
)


async def _materialize(gym: GymAct, principal: str | None = None):
    gym.register_provider(MemoryProvider())
    intent = MaterializationIntent(provider="memory", principal=principal)
    result = await gym.materialize(intent)
    assert result.accepted, result.receipt.reason
    return result


async def test_allowlist_scope_refuses_excluded_capability_and_permits_included_one():
    gym = GymAct()
    materialization = await _materialize(gym, principal="urn:gymact:agent:alice")
    episode_id = materialization.episode.episode_id
    do_capabilities = [c for c in gym.capabilities(episode_id) if c.consequence.value == "DO"]
    assert len(do_capabilities) >= 2, "need >=2 DO capabilities to prove exclusion vs inclusion"
    included, excluded = do_capabilities[0], do_capabilities[1]

    scoped_gym = GymAct(
        capability_scope=AllowListCapabilityScope(
            {"urn:gymact:agent:alice": frozenset({included.iri})}
        )
    )
    scoped_gym.register_provider(MemoryProvider())
    scoped_materialization = await scoped_gym.materialize(
        MaterializationIntent(provider="memory", principal="urn:gymact:agent:alice")
    )
    assert scoped_materialization.accepted
    scoped_episode_id = scoped_materialization.episode.episode_id

    refused = await scoped_gym.act(
        ActuationIntent(
            episode_id=scoped_episode_id,
            capability=excluded.iri,
            principal="urn:gymact:agent:alice",
        )
    )
    assert not refused.accepted
    assert refused.receipt.reason == "CAPABILITY_NOT_IN_SCOPE"

    permitted = await scoped_gym.act(
        ActuationIntent(
            episode_id=scoped_episode_id,
            capability=included.iri,
            principal="urn:gymact:agent:alice",
        )
    )
    assert permitted.receipt.reason != "CAPABILITY_NOT_IN_SCOPE"


async def test_default_allow_all_scope_is_zero_behavior_change_for_unscoped_gymact():
    gym = GymAct()
    materialization = await _materialize(gym)
    episode_id = materialization.episode.episode_id
    do_capabilities = [c for c in gym.capabilities(episode_id) if c.consequence.value == "DO"]
    assert do_capabilities

    result = await gym.act(
        ActuationIntent(episode_id=episode_id, capability=do_capabilities[0].iri)
    )
    assert result.receipt.reason != "CAPABILITY_NOT_IN_SCOPE"

    explicit_gym = GymAct(capability_scope=AllowAllCapabilityScope())
    explicit_materialization = await _materialize(explicit_gym)
    explicit_episode_id = explicit_materialization.episode.episode_id
    explicit_do = [
        c for c in explicit_gym.capabilities(explicit_episode_id) if c.consequence.value == "DO"
    ]
    explicit_result = await explicit_gym.act(
        ActuationIntent(episode_id=explicit_episode_id, capability=explicit_do[0].iri)
    )
    assert explicit_result.receipt.reason != "CAPABILITY_NOT_IN_SCOPE"


async def test_principal_threads_from_intent_into_real_receipt_on_every_operation():
    gym = GymAct()
    materialization = await _materialize(gym, principal="urn:gymact:agent:bob")
    assert materialization.receipt.principal == "urn:gymact:agent:bob"
    episode_id = materialization.episode.episode_id

    do_capabilities = [c for c in gym.capabilities(episode_id) if c.consequence.value == "DO"]
    result = await gym.act(
        ActuationIntent(
            episode_id=episode_id,
            capability=do_capabilities[0].iri,
            principal="urn:gymact:agent:bob",
        )
    )
    assert result.receipt.principal == "urn:gymact:agent:bob"
