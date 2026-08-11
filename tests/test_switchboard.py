"""Chicago-style: real `GymAct` episodes against the real
`SwitchboardProvider` (`gymact.gyms.switchboard`) -- conditional effect
(`engage_master`), negative-effect trap (`reset_pair`), and seeded decoy
switches.

No mocks: real kernel, real environment, real authority resolvers, real
state-based assertions on returned/observed dicts.
"""

from __future__ import annotations

from gymact import AllowListAuthorityResolver, GymAct, MaterializationIntent
from gymact.gyms.switchboard import SWITCHBOARD_CAPABILITIES, SwitchboardProvider
from gymact.models import ActuationIntent, Standing

TOGGLE_SWITCH = "urn:gymact:switchboard:capability:toggle_switch"
ENGAGE_MASTER = "urn:gymact:switchboard:capability:engage_master"
RESET_PAIR = "urn:gymact:switchboard:capability:reset_pair"
READ_BOARD = "urn:gymact:switchboard:capability:read_board"
AUTHORITY = "urn:test:switchboard-authority"


def _gym() -> GymAct:
    gym = GymAct(authority_resolver=AllowListAuthorityResolver({AUTHORITY}))
    gym.register_provider(SwitchboardProvider())
    return gym


async def _materialize(gym: GymAct, config: dict) -> str:
    materialization = await gym.materialize(
        MaterializationIntent(provider="switchboard", config=config)
    )
    assert materialization.accepted is True, materialization.receipt.reason
    return materialization.episode.episode_id


async def _toggle(gym: GymAct, episode_id: str, index: int):
    return await gym.act(
        ActuationIntent(
            episode_id=episode_id,
            capability=TOGGLE_SWITCH,
            payload={"index": index},
            authority_ref=AUTHORITY,
        )
    )


def test_capability_shapes_match_module_constant() -> None:
    assert len(SWITCHBOARD_CAPABILITIES) == 4
    bindings = {c.binding for c in SWITCHBOARD_CAPABILITIES}
    assert bindings == {"toggle_switch", "engage_master", "reset_pair", "read_board"}
    for cap in SWITCHBOARD_CAPABILITIES:
        if cap.binding == "read_board":
            assert cap.consequence.value == "READ"
        else:
            assert cap.consequence.value == "DO"


async def test_materialize_creates_real_episode_with_all_switches_off() -> None:
    gym = _gym()
    episode_id = await _materialize(gym, {"seed": 1, "n_switches": 5})

    observation = await gym.observe(episode_id)
    assert observation.state["master"] is False
    assert observation.state["solved"] is False
    assert observation.state["switch_0"] is False
    assert observation.state["switch_1"] is False

    await gym.teardown(episode_id, authority_ref=AUTHORITY)


async def test_full_episode_solves_the_board_using_the_seeded_required_decoys() -> None:
    """Drives the real environment to solved=True by discovering the real
    seeded `required` decoy set through the environment's own attribute
    (the equivalent of a discovery agent probing switch effects), then
    toggling switches 0/1 plus every required decoy before engaging master."""
    gym = _gym()
    episode_id = await _materialize(gym, {"seed": 9, "n_switches": 6})
    env = gym._episodes[episode_id].environment
    required = env.required

    result0 = await _toggle(gym, episode_id, 0)
    assert result0.accepted is True
    result1 = await _toggle(gym, episode_id, 1)
    assert result1.accepted is True
    for index in required:
        result = await _toggle(gym, episode_id, index)
        assert result.accepted is True

    engaged = await gym.act(
        ActuationIntent(episode_id=episode_id, capability=ENGAGE_MASTER, authority_ref=AUTHORITY)
    )
    assert engaged.accepted is True
    assert engaged.effect["applicable"] is True

    observation = await gym.observe(episode_id)
    assert observation.state["solved"] is True
    assert observation.state["master"] is True

    verification = await gym.verify(episode_id, {"solved": True})
    assert verification.passed is True

    await gym.teardown(episode_id, authority_ref=AUTHORITY)


async def test_engage_master_before_switches_0_and_1_are_on_is_refused_as_inapplicable() -> None:
    gym = _gym()
    episode_id = await _materialize(gym, {"seed": 2, "n_switches": 5})

    result = await gym.act(
        ActuationIntent(episode_id=episode_id, capability=ENGAGE_MASTER, authority_ref=AUTHORITY)
    )
    assert result.accepted is True
    assert result.effect["applicable"] is False
    assert "precondition unmet" in result.effect["result_text"]

    observation = await gym.observe(episode_id)
    assert observation.state["master"] is False

    await gym.teardown(episode_id, authority_ref=AUTHORITY)


async def test_engage_master_is_applicable_but_inert_when_switches_partially_on() -> None:
    """Distinguishes a conditional effect from an error: engage_master is
    accepted (act() admits it) and reports applicable=False -- not an
    exception -- when only switch 0 is on, and remains inert (master stays
    False) even though the action itself succeeded at the kernel layer."""
    gym = _gym()
    episode_id = await _materialize(gym, {"seed": 3, "n_switches": 5})

    toggled = await _toggle(gym, episode_id, 0)
    assert toggled.accepted is True

    result = await gym.act(
        ActuationIntent(episode_id=episode_id, capability=ENGAGE_MASTER, authority_ref=AUTHORITY)
    )
    assert result.accepted is True
    assert result.effect["applicable"] is False
    assert result.effect["before"]["master"] is False
    assert result.effect["after"]["master"] is False

    await gym.teardown(episode_id, authority_ref=AUTHORITY)


async def test_reset_pair_is_a_lawful_negative_effect_that_regresses_progress() -> None:
    """reset_pair is always applicable and always undoes switches 0/1 -- a
    real trap, distinct from the conditional-but-inert engage_master case."""
    gym = _gym()
    episode_id = await _materialize(gym, {"seed": 4, "n_switches": 5})

    await _toggle(gym, episode_id, 0)
    await _toggle(gym, episode_id, 1)
    engaged = await gym.act(
        ActuationIntent(episode_id=episode_id, capability=ENGAGE_MASTER, authority_ref=AUTHORITY)
    )
    assert engaged.accepted is True
    assert engaged.effect["applicable"] is True

    reset = await gym.act(
        ActuationIntent(episode_id=episode_id, capability=RESET_PAIR, authority_ref=AUTHORITY)
    )
    assert reset.accepted is True
    assert reset.effect["applicable"] is True
    assert reset.effect["after"]["switch_0"] is False
    assert reset.effect["after"]["switch_1"] is False

    observation = await gym.observe(episode_id)
    assert observation.state["switch_0"] is False
    assert observation.state["switch_1"] is False
    # master itself is untouched by reset_pair (only re-toggling could
    # re-derive solved=False through required_on/master combination), but
    # the pair regression itself is the real, checkable effect under test.

    await gym.teardown(episode_id, authority_ref=AUTHORITY)


async def test_checkpoint_restore_round_trip_recovers_real_switch_state() -> None:
    gym = _gym()
    episode_id = await _materialize(gym, {"seed": 5, "n_switches": 5})

    await _toggle(gym, episode_id, 0)
    checkpoint = await gym.checkpoint(episode_id)
    assert checkpoint["switches"][0] is True

    await _toggle(gym, episode_id, 1)
    advanced = await gym.observe(episode_id)
    assert advanced.state["switch_1"] is True

    await gym.restore(episode_id, checkpoint, authority_ref=AUTHORITY)

    restored = await gym.observe(episode_id)
    assert restored.state["switch_0"] is True
    assert restored.state["switch_1"] is False

    await gym.teardown(episode_id, authority_ref=AUTHORITY)


async def test_read_board_via_act_is_refused_reads_must_use_observe() -> None:
    gym = _gym()
    episode_id = await _materialize(gym, {"seed": 6, "n_switches": 5})

    read_attempt = await gym.act(
        ActuationIntent(episode_id=episode_id, capability=READ_BOARD, authority_ref=AUTHORITY)
    )
    assert read_attempt.accepted is False

    await gym.teardown(episode_id, authority_ref=AUTHORITY)


async def test_do_capability_is_refused_without_admitted_authority() -> None:
    """A plain GymAct() defaults to DenyAuthorityResolver -- toggle_switch
    must be refused when requires_authority=True, not silently authorized."""
    gym = GymAct()
    gym.register_provider(SwitchboardProvider())
    materialization = await gym.materialize(
        MaterializationIntent(
            provider="switchboard",
            config={"seed": 1, "n_switches": 5, "requires_authority": True},
        )
    )
    assert materialization.accepted is True, materialization.receipt.reason
    episode_id = materialization.episode.episode_id

    result = await gym.act(
        ActuationIntent(
            episode_id=episode_id, capability=TOGGLE_SWITCH, payload={"index": 0}
        )
    )

    assert result.accepted is False
    assert result.standing is Standing.REFUSED

    await gym.teardown(episode_id)
