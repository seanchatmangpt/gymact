"""Chicago-style: real `GymAct` episodes against the real
`ResourceFlowProvider` (`gymact.gyms.resource_flow`) -- capacitated numeric
pools with a dedicated test for the `burn_catalyst` irreversible dead-end.

No mocks: real kernel, real environment, real authority resolvers, real
state-based assertions on returned/observed dicts.
"""

from __future__ import annotations

from gymact import AllowListAuthorityResolver, GymAct, MaterializationIntent
from gymact.gyms.resource_flow import RESOURCE_FLOW_CAPABILITIES, ResourceFlowProvider
from gymact.models import ActuationIntent, Standing

MINE = "urn:gymact:resource-flow:capability:mine"
REFINE = "urn:gymact:resource-flow:capability:refine"
ASSEMBLE = "urn:gymact:resource-flow:capability:assemble"
BURN_CATALYST = "urn:gymact:resource-flow:capability:burn_catalyst"
READ_POOLS = "urn:gymact:resource-flow:capability:read_pools"
AUTHORITY = "urn:test:resource-flow-authority"


def _gym() -> GymAct:
    gym = GymAct(authority_resolver=AllowListAuthorityResolver({AUTHORITY}))
    gym.register_provider(ResourceFlowProvider())
    return gym


async def _materialize(gym: GymAct, config: dict) -> str:
    materialization = await gym.materialize(
        MaterializationIntent(provider="resource-flow", config=config)
    )
    assert materialization.accepted is True, materialization.receipt.reason
    return materialization.episode.episode_id


async def _act(gym: GymAct, episode_id: str, capability: str):
    return await gym.act(
        ActuationIntent(episode_id=episode_id, capability=capability, authority_ref=AUTHORITY)
    )


def test_capability_shapes_match_module_constant() -> None:
    assert len(RESOURCE_FLOW_CAPABILITIES) == 5
    bindings = {c.binding for c in RESOURCE_FLOW_CAPABILITIES}
    assert bindings == {"mine", "refine", "assemble", "burn_catalyst", "read_pools"}
    for cap in RESOURCE_FLOW_CAPABILITIES:
        if cap.binding == "read_pools":
            assert cap.consequence.value == "READ"
        else:
            assert cap.consequence.value == "DO"


async def test_materialize_creates_real_episode_with_empty_pools() -> None:
    gym = _gym()
    episode_id = await _materialize(gym, {"seed": 1, "capacity": 8, "target": 3})

    observation = await gym.observe(episode_id)
    assert observation.state["raw"] == 0
    assert observation.state["refined"] == 0
    assert observation.state["output"] == 0
    assert observation.state["catalyst"] is True
    assert observation.state["solved"] is False

    await gym.teardown(episode_id, authority_ref=AUTHORITY)


async def test_full_episode_reaches_target_output_without_burning_catalyst() -> None:
    gym = _gym()
    episode_id = await _materialize(gym, {"seed": 2, "capacity": 8, "target": 3})

    observation = await gym.observe(episode_id)
    while observation.state["output"] < observation.state["target"]:
        if observation.state["refined"] < 1 and observation.state["raw"] < 1:
            result = await _act(gym, episode_id, MINE)
            assert result.accepted is True
        elif observation.state["refined"] < 1:
            result = await _act(gym, episode_id, REFINE)
            assert result.accepted is True
        else:
            result = await _act(gym, episode_id, ASSEMBLE)
            assert result.accepted is True
        observation = await gym.observe(episode_id)

    assert observation.state["solved"] is True

    verification = await gym.verify(episode_id, {"solved": True})
    assert verification.passed is True

    await gym.teardown(episode_id, authority_ref=AUTHORITY)


async def test_refine_with_no_raw_tokens_is_refused_as_inapplicable() -> None:
    gym = _gym()
    episode_id = await _materialize(gym, {"seed": 3, "capacity": 8, "target": 3})

    result = await _act(gym, episode_id, REFINE)
    assert result.accepted is True
    assert result.effect["applicable"] is False
    assert "no raw tokens" in result.effect["result_text"]

    observation = await gym.observe(episode_id)
    assert observation.state["refined"] == 0

    await gym.teardown(episode_id, authority_ref=AUTHORITY)


async def test_burn_catalyst_permanently_disables_refine_and_can_dead_end() -> None:
    """capacity=8, target=8: burning the catalyst immediately with empty
    pools guarantees output+refined < target forever (refine is dead), so
    `_dead_end()` must report True and refine must stay refused."""
    gym = _gym()
    episode_id = await _materialize(gym, {"seed": 4, "capacity": 8, "target": 8})

    burned = await _act(gym, episode_id, BURN_CATALYST)
    assert burned.accepted is True
    assert burned.effect["applicable"] is True
    assert burned.effect["after"]["catalyst"] is False
    assert burned.effect["after"]["dead_end"] is True

    # refine is now permanently unavailable, regardless of raw stock.
    mined = await _act(gym, episode_id, MINE)
    assert mined.accepted is True

    refine_attempt = await _act(gym, episode_id, REFINE)
    assert refine_attempt.accepted is True
    assert refine_attempt.effect["applicable"] is False
    assert "permanently unavailable" in refine_attempt.effect["result_text"]

    # Burning again is a one-shot trap, not repeatable.
    burned_again = await _act(gym, episode_id, BURN_CATALYST)
    assert burned_again.accepted is True
    assert burned_again.effect["applicable"] is False
    assert "already burned" in burned_again.effect["result_text"]

    observation = await gym.observe(episode_id)
    assert observation.state["solved"] is False
    assert observation.state["dead_end"] is True

    await gym.teardown(episode_id, authority_ref=AUTHORITY)


async def test_checkpoint_restore_round_trip_recovers_real_pool_levels() -> None:
    gym = _gym()
    episode_id = await _materialize(gym, {"seed": 5, "capacity": 8, "target": 3})

    mined = await _act(gym, episode_id, MINE)
    assert mined.accepted is True
    checkpoint = await gym.checkpoint(episode_id)
    raw_after_mine = checkpoint["raw"]
    assert raw_after_mine > 0

    refined = await _act(gym, episode_id, REFINE)
    assert refined.accepted is True
    advanced = await gym.observe(episode_id)
    assert advanced.state["refined"] >= 1

    await gym.restore(episode_id, checkpoint, authority_ref=AUTHORITY)

    restored = await gym.observe(episode_id)
    assert restored.state["raw"] == raw_after_mine
    assert restored.state["refined"] == 0

    await gym.teardown(episode_id, authority_ref=AUTHORITY)


async def test_read_pools_via_act_is_refused_reads_must_use_observe() -> None:
    gym = _gym()
    episode_id = await _materialize(gym, {"seed": 6, "capacity": 8, "target": 3})

    read_attempt = await _act(gym, episode_id, READ_POOLS)
    assert read_attempt.accepted is False

    await gym.teardown(episode_id, authority_ref=AUTHORITY)


async def test_do_capability_is_refused_without_admitted_authority() -> None:
    """A plain GymAct() defaults to DenyAuthorityResolver -- mine must be
    refused when requires_authority=True, not silently authorized."""
    gym = GymAct()
    gym.register_provider(ResourceFlowProvider())
    materialization = await gym.materialize(
        MaterializationIntent(
            provider="resource-flow",
            config={"seed": 1, "capacity": 8, "target": 3, "requires_authority": True},
        )
    )
    assert materialization.accepted is True, materialization.receipt.reason
    episode_id = materialization.episode.episode_id

    result = await gym.act(ActuationIntent(episode_id=episode_id, capability=MINE))

    assert result.accepted is False
    assert result.standing is Standing.REFUSED

    await gym.teardown(episode_id)
