"""Chicago-style: real GymAct episodes against three bounded, self-contained
local gyms built for blind-discovery structural diversity.

No mocks anywhere -- `GymAct.materialize` really instantiates the real
`SwitchboardEnvironment` / `ResourceFlowEnvironment` / `LockAndKeyEnvironment`,
`gym.act` really mutates them, and every assertion is on real final STATE read
back through `gym.observe` / `gym.verify`, never on interactions.

Unlike `test_cube_counter.py` there is no `require_standing` gate here: these
three gyms are pure Python with no optional dependency, no network, no Docker
and no subprocess, so there is nothing that could legitimately degrade. If they
fail, they fail.

What these gyms add over `cube_counter`'s monotone counter, and what each test
below actually pins down as real state:

* switchboard   -- conditional effect, negative effect, decoy switches
* resource-flow -- capacitated pools, irreversible consumption, real dead end
* lock-and-key  -- ordered hidden prerequisites, reversible + irreversible acts
"""

from __future__ import annotations

import pytest

from gymact import GymAct, MaterializationIntent
from gymact.gyms.lock_and_key import LockAndKeyProvider
from gymact.gyms.resource_flow import ResourceFlowProvider
from gymact.gyms.switchboard import SwitchboardProvider
from gymact.models import ActuationIntent, Operation, Standing
from gymact.process import ConformanceChecker

SW = "urn:gymact:switchboard:capability:"
RF = "urn:gymact:resource-flow:capability:"
LK = "urn:gymact:lock-and-key:capability:"


async def _act(gym: GymAct, episode_id: str, capability: str, **payload):
    return await gym.act(
        ActuationIntent(episode_id=episode_id, capability=capability, payload=payload)
    )


async def _start(provider, config: dict) -> tuple[GymAct, str]:
    gym = GymAct()
    gym.register_provider(provider)
    materialization = await gym.materialize(
        MaterializationIntent(provider=provider.name, config=config)
    )
    assert materialization.accepted is True
    return gym, materialization.episode.episode_id


# --------------------------------------------------------------------------
# switchboard
# --------------------------------------------------------------------------


async def test_switchboard_master_is_conditional_on_both_switches() -> None:
    gym, ep = await _start(SwitchboardProvider(), {"seed": 7, "n_switches": 6})

    first = await gym.observe(ep)
    assert first.state["master"] is False
    assert first.state["switch_0"] is False
    assert first.state["n_switches"] == 6
    assert first.state["toggles"] == 0

    # Engaging with neither switch on is lawful but INERT: real state unchanged.
    inert = await _act(gym, ep, SW + "engage_master")
    assert inert.accepted is True
    assert (await gym.observe(ep)).state["master"] is False

    await _act(gym, ep, SW + "toggle_switch", index=0)
    # Still only one of the two preconditions met.
    await _act(gym, ep, SW + "engage_master")
    assert (await gym.observe(ep)).state["master"] is False

    await _act(gym, ep, SW + "toggle_switch", index=1)
    await _act(gym, ep, SW + "engage_master")
    after = await gym.observe(ep)
    assert after.state["master"] is True
    assert after.state["toggles"] == 2

    await gym.teardown(ep)


async def test_switchboard_reset_pair_is_a_real_negative_effect() -> None:
    gym, ep = await _start(SwitchboardProvider(), {"seed": 7, "n_switches": 6})

    await _act(gym, ep, SW + "toggle_switch", index=0)
    await _act(gym, ep, SW + "toggle_switch", index=1)
    assert (await gym.observe(ep)).state["switch_0"] is True

    result = await _act(gym, ep, SW + "reset_pair")
    assert result.accepted is True

    after = await gym.observe(ep)
    assert after.state["switch_0"] is False
    assert after.state["switch_1"] is False
    # Negative on the switches, but the latch itself is not undone.
    assert after.state["master"] is False

    await gym.teardown(ep)


async def test_switchboard_reaches_goal_and_decoys_are_irrelevant() -> None:
    gym, ep = await _start(SwitchboardProvider(), {"seed": 7, "n_switches": 6})
    env = gym._state(ep).environment  # real environment, for its seeded goal
    required = env.required
    assert len(required) == 2
    assert all(i >= 2 for i in required)

    decoys = [i for i in range(2, 6) if i not in required]
    assert decoys, "seed 7 / n_switches 6 must leave at least one decoy"

    for i in decoys:
        await _act(gym, ep, SW + "toggle_switch", index=i)
    mid = await gym.observe(ep)
    assert mid.state["solved"] is False
    assert mid.state["required_on"] == 0

    await _act(gym, ep, SW + "toggle_switch", index=0)
    await _act(gym, ep, SW + "toggle_switch", index=1)
    await _act(gym, ep, SW + "engage_master")
    for i in required:
        await _act(gym, ep, SW + "toggle_switch", index=i)

    verification = await gym.verify(ep, {"solved": True, "master": True, "required_on": 2})
    assert verification.passed is True
    await gym.teardown(ep)


async def test_switchboard_is_seed_deterministic_and_seed_sensitive() -> None:
    a = await _start(SwitchboardProvider(), {"seed": 11, "n_switches": 8})
    b = await _start(SwitchboardProvider(), {"seed": 11, "n_switches": 8})
    c = await _start(SwitchboardProvider(), {"seed": 12, "n_switches": 8})

    ra = a[0]._state(a[1]).environment.required
    rb = b[0]._state(b[1]).environment.required
    rc = c[0]._state(c[1]).environment.required

    assert ra == rb
    assert ra != rc

    for gym, ep in (a, b, c):
        await gym.teardown(ep)


async def test_switchboard_checkpoint_restore_round_trips_real_state() -> None:
    gym, ep = await _start(SwitchboardProvider(), {"seed": 7, "n_switches": 6})

    await _act(gym, ep, SW + "toggle_switch", index=0)
    saved_observation = await gym.observe(ep)
    checkpoint = await gym.checkpoint(ep)

    await _act(gym, ep, SW + "toggle_switch", index=1)
    await _act(gym, ep, SW + "engage_master")
    assert (await gym.observe(ep)).state["master"] is True

    restored = await gym.restore(ep, checkpoint)
    assert restored.standing == Standing.ALIVE
    assert (await gym.observe(ep)).state == saved_observation.state

    await gym.teardown(ep)


# --------------------------------------------------------------------------
# resource-flow
# --------------------------------------------------------------------------


async def test_resource_flow_reaches_target_through_the_full_chain() -> None:
    gym, ep = await _start(
        ResourceFlowProvider(), {"seed": 3, "capacity": 8, "target": 3}
    )

    start = await gym.observe(ep)
    assert start.state["raw"] == 0
    assert start.state["catalyst"] is True
    assert start.state["dead_end"] is False

    for _ in range(3):
        await _act(gym, ep, RF + "mine")
    assert (await gym.observe(ep)).state["raw"] >= 3

    for _ in range(3):
        await _act(gym, ep, RF + "refine")
    assert (await gym.observe(ep)).state["refined"] == 3

    for _ in range(3):
        await _act(gym, ep, RF + "assemble")

    verification = await gym.verify(ep, {"output": 3, "solved": True, "dead_end": False})
    assert verification.passed is True
    await gym.teardown(ep)


async def test_resource_flow_burning_the_catalyst_is_an_irreversible_dead_end() -> None:
    gym, ep = await _start(
        ResourceFlowProvider(), {"seed": 3, "capacity": 8, "target": 3}
    )

    burn = await _act(gym, ep, RF + "burn_catalyst")
    assert burn.accepted is True
    after_burn = await gym.observe(ep)
    assert after_burn.state["catalyst"] is False
    assert after_burn.state["output"] < 3
    assert after_burn.state["dead_end"] is True

    # Every remaining action is lawful and executable, and none escapes.
    await _act(gym, ep, RF + "mine")
    await _act(gym, ep, RF + "mine")
    await _act(gym, ep, RF + "refine")
    await _act(gym, ep, RF + "assemble")
    await _act(gym, ep, RF + "burn_catalyst")

    stuck = await gym.observe(ep)
    assert stuck.state["refined"] == 0
    assert stuck.state["solved"] is False
    assert stuck.state["dead_end"] is True
    assert stuck.state["raw"] > 0  # raw kept accumulating; it just cannot help

    await gym.teardown(ep)


async def test_resource_flow_pools_are_really_capped_at_capacity() -> None:
    gym, ep = await _start(
        ResourceFlowProvider(), {"seed": 5, "capacity": 4, "target": 2}
    )

    for _ in range(20):
        await _act(gym, ep, RF + "mine")

    capped = await gym.observe(ep)
    assert capped.state["raw"] == 4
    assert capped.state["capacity"] == 4

    await gym.teardown(ep)


async def test_resource_flow_refine_before_mining_changes_nothing() -> None:
    gym, ep = await _start(
        ResourceFlowProvider(), {"seed": 5, "capacity": 4, "target": 2}
    )

    before = await gym.observe(ep)
    result = await _act(gym, ep, RF + "refine")
    after = await gym.observe(ep)

    assert result.accepted is True  # lawful, but inapplicable
    assert after.state == before.state

    await gym.teardown(ep)


async def test_resource_flow_is_seed_deterministic_and_seed_sensitive() -> None:
    rates = {}
    for seed in (1, 1, 2, 3, 4, 5):
        gym, ep = await _start(
            ResourceFlowProvider(), {"seed": seed, "capacity": 6, "target": 2}
        )
        rates.setdefault(seed, []).append(gym._state(ep).environment.mine_rate)
        await gym.teardown(ep)

    assert rates[1][0] == rates[1][1]
    assert len({v[0] for v in rates.values()}) > 1


# --------------------------------------------------------------------------
# lock-and-key
# --------------------------------------------------------------------------


async def test_lock_and_key_opens_the_final_lock_in_hidden_order() -> None:
    gym, ep = await _start(LockAndKeyProvider(), {"seed": 9, "depth": 4})
    env = gym._state(ep).environment

    start = await gym.observe(ep)
    assert start.state["depth"] == 4
    assert start.state["locks_open"] == 0
    assert start.state["held_key"] == -1
    assert start.state["holding_key"] is False
    assert "perm" not in start.state  # hidden order is never disclosed

    for _ in range(4):
        needed = env.required_key()
        await _act(gym, ep, LK + "pick_key", key=needed)
        assert (await gym.observe(ep)).state["held_key"] == needed
        await _act(gym, ep, LK + "open_lock")

    verification = await gym.verify(
        ep, {"locks_open": 4, "final_open": True, "solved": True, "rack_jammed": False}
    )
    assert verification.passed is True
    await gym.teardown(ep)


async def test_lock_and_key_wrong_key_does_not_advance_and_is_reversible() -> None:
    gym, ep = await _start(LockAndKeyProvider(), {"seed": 9, "depth": 4})
    env = gym._state(ep).environment
    needed = env.required_key()
    wrong = next(k for k in range(4) if k != needed)

    await _act(gym, ep, LK + "pick_key", key=wrong)
    await _act(gym, ep, LK + "open_lock")
    blocked = await gym.observe(ep)
    assert blocked.state["locks_open"] == 0
    assert blocked.state["held_key"] == wrong

    # Reversible: drop it and the hand really is empty again.
    await _act(gym, ep, LK + "drop_key")
    assert (await gym.observe(ep)).state["held_key"] == -1

    await _act(gym, ep, LK + "pick_key", key=needed)
    await _act(gym, ep, LK + "open_lock")
    assert (await gym.observe(ep)).state["locks_open"] == 1

    await gym.teardown(ep)


async def test_lock_and_key_force_latch_is_a_deceptive_but_lawful_dead_end() -> None:
    gym, ep = await _start(LockAndKeyProvider(), {"seed": 9, "depth": 4})

    forced = await _act(gym, ep, LK + "force_latch")
    assert forced.accepted is True

    after = await gym.observe(ep)
    assert after.state["locks_open"] == 1  # real, visible "progress"
    assert after.state["rack_jammed"] is True
    assert after.state["dead_end"] is True

    # Every remaining lawful action, exhaustively: none reaches the goal.
    for _ in range(6):
        for key in range(4):
            await _act(gym, ep, LK + "pick_key", key=key)
        await _act(gym, ep, LK + "drop_key")
        await _act(gym, ep, LK + "open_lock")

    stuck = await gym.observe(ep)
    assert stuck.state["locks_open"] == 1
    assert stuck.state["held_key"] == -1
    assert stuck.state["solved"] is False
    assert stuck.state["dead_end"] is True

    await gym.teardown(ep)


async def test_lock_and_key_forcing_the_last_lock_still_solves() -> None:
    """The dead end is depth-dependent, not a blanket ban -- forcing the ONLY
    remaining lock does reach the goal, so `dead_end` is a real predicate and
    not a constant."""
    gym, ep = await _start(LockAndKeyProvider(), {"seed": 9, "depth": 1})

    await _act(gym, ep, LK + "force_latch")

    solved = await gym.observe(ep)
    assert solved.state["locks_open"] == 1
    assert solved.state["solved"] is True
    assert solved.state["dead_end"] is False

    await gym.teardown(ep)


async def test_lock_and_key_is_seed_deterministic_and_seed_sensitive() -> None:
    perms = []
    for seed in (21, 21, 22):
        gym, ep = await _start(LockAndKeyProvider(), {"seed": seed, "depth": 5})
        perms.append(gym._state(ep).environment._perm)
        await gym.teardown(ep)

    assert perms[0] == perms[1]
    assert perms[0] != perms[2]


# --------------------------------------------------------------------------
# cross-gym: typed-state surface and receipted lifecycle
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("provider_factory", "config"),
    [
        (SwitchboardProvider, {"seed": 7, "n_switches": 6}),
        (ResourceFlowProvider, {"seed": 3, "capacity": 8, "target": 3}),
        (LockAndKeyProvider, {"seed": 9, "depth": 4}),
    ],
)
async def test_observation_mixes_bool_and_int_for_the_typed_classifier(
    provider_factory, config: dict
) -> None:
    gym, ep = await _start(provider_factory(), config)

    state = (await gym.observe(ep)).state
    kinds = {type(value) for value in state.values()}
    assert bool in kinds
    assert int in kinds
    assert any(isinstance(v, bool) for v in state.values())
    assert any(isinstance(v, int) and not isinstance(v, bool) for v in state.values())

    await gym.teardown(ep)


@pytest.mark.parametrize(
    ("provider_factory", "config", "capability"),
    [
        (SwitchboardProvider, {"seed": 7, "n_switches": 6}, SW + "reset_pair"),
        (ResourceFlowProvider, {"seed": 3, "capacity": 8, "target": 3}, RF + "mine"),
        (LockAndKeyProvider, {"seed": 9, "depth": 4}, LK + "force_latch"),
    ],
)
async def test_episode_is_receipted_and_conformant(
    provider_factory, config: dict, capability: str
) -> None:
    provider = provider_factory()
    gym = GymAct()
    gym.register_provider(provider)
    materialization = await gym.materialize(
        MaterializationIntent(provider=provider.name, config=config)
    )
    receipts = [materialization.receipt]
    ep = materialization.episode.episode_id

    for _ in range(2):
        result = await gym.act(ActuationIntent(episode_id=ep, capability=capability))
        assert result.accepted is True
        receipts.append(result.receipt)

    receipts.append(await gym.teardown(ep))
    operations = [r.operation for r in receipts]

    assert operations == [
        Operation.MATERIALIZE,
        Operation.ACT,
        Operation.ACT,
        Operation.TEARDOWN,
    ]
    assert all(r.standing == "ALIVE" for r in receipts)

    conformance = ConformanceChecker().check(operations)
    assert conformance.conformant is True
    assert conformance.deviations == []


@pytest.mark.parametrize(
    ("provider_factory", "config"),
    [
        (SwitchboardProvider, {"seed": 7, "n_switches": 6}),
        (ResourceFlowProvider, {"seed": 3, "capacity": 8, "target": 3}),
        (LockAndKeyProvider, {"seed": 9, "depth": 4}),
    ],
)
async def test_provider_requires_no_authority_by_default(
    provider_factory, config: dict
) -> None:
    provider = provider_factory()
    assert provider.materialization_requires_authority is False

    gym, ep = await _start(provider, config)
    environment = gym._state(ep).environment
    assert environment.requires_authority is False
    assert len(environment.capabilities()) >= 4
    assert any(c.consequence == "READ" for c in environment.capabilities())
    assert any(c.consequence == "DO" for c in environment.capabilities())

    await gym.teardown(ep)
