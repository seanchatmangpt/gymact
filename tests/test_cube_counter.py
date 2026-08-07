"""Chicago-style: a real GymAct episode driven against a real, externally
published benchmark (CUBE's `counter-cube` reference task) -- the first bridge
from GymAct's kernel to a real gym in the ForwardBench corpus
(~/autofde-lab/docs/papers/gym-lock.ttl: `vendor-cube-standard`, smoke
standing SCENARIO_RUNS as of this session).

No mocked task, no mocked tool, no mocked environment -- `GymAct.materialize`
really instantiates `CubeCounterEnvironment`, which really wraps a real
`counter_cube.task.ReachTargetTask`.

This module claims standing "LOCAL_GYM:cube-counter" -- deliberately not
anything cloud-flavored, since `counter-cube` is CUBE's own no-Docker,
no-network reference task and never claims otherwise. Per
`gymact.standing.require_standing`, the real thing is the default: if the
optional `cube` extra isn't installed, this module now FAILS unless the
run explicitly sets `GYMACT_ALLOW_DEGRADED_STANDINGS` to include
"LOCAL_GYM:cube-counter" (or "*") -- a skip here is something a run must
opt into, never something it silently gets.
"""

from __future__ import annotations

import importlib.util

import pytest

from gymact.standing import require_standing

require_standing(
    "LOCAL_GYM:cube-counter",
    available=importlib.util.find_spec("counter_cube") is not None,
    reason="optional 'cube' extra not installed (uv sync --extra cube / --all-extras)",
)

from gymact import AllowListAuthorityResolver, GymAct, MaterializationIntent  # noqa: E402
from gymact.gyms.cube_counter import CubeCounterProvider  # noqa: E402
from gymact.models import ActuationIntent, Operation, Standing  # noqa: E402
from gymact.process import ConformanceChecker  # noqa: E402

INCREMENT_CAPABILITY = "urn:gymact:cube-counter:capability:increment"
AUTHORITY = "urn:test:cube-counter-authority"


@pytest.fixture
def gym() -> GymAct:
    orchestrator = GymAct()
    orchestrator.register_provider(CubeCounterProvider())
    return orchestrator


async def _run_real_counter_episode(gym: GymAct) -> tuple[list, list[Operation]]:
    receipts = []

    materialization = await gym.materialize(
        MaterializationIntent(provider="cube-counter", config={"target": 3})
    )
    assert materialization.accepted is True
    receipts.append(materialization.receipt)
    episode_id = materialization.episode.episode_id

    observation = await gym.observe(episode_id)
    assert observation.state["counter"] == 0

    for _ in range(3):
        result = await gym.act(
            ActuationIntent(
                episode_id=episode_id,
                capability=INCREMENT_CAPABILITY,
            )
        )
        assert result.accepted is True
        receipts.append(result.receipt)

    verification = await gym.verify(episode_id, {"counter": 3, "solved": True})
    assert verification.passed is True

    teardown_receipt = await gym.teardown(episode_id)
    receipts.append(teardown_receipt)

    return receipts, [r.operation for r in receipts]


async def test_real_counter_episode_reaches_target_and_is_receipted() -> None:
    gym_instance = GymAct()
    gym_instance.register_provider(CubeCounterProvider())

    receipts, operations = await _run_real_counter_episode(gym_instance)

    assert operations == [
        Operation.MATERIALIZE,
        Operation.ACT,
        Operation.ACT,
        Operation.ACT,
        Operation.TEARDOWN,
    ]
    assert all(r.standing == "ALIVE" for r in receipts)


async def test_real_counter_episode_replays_conformant_against_declared_lifecycle() -> None:
    gym_instance = GymAct()
    gym_instance.register_provider(CubeCounterProvider())

    _receipts, operations = await _run_real_counter_episode(gym_instance)

    result = ConformanceChecker().check(operations)

    assert result.conformant is True
    assert result.deviations == []


async def test_acting_before_materialize_is_named_as_an_illegal_transition() -> None:
    # A synthetic, out-of-order operation trace (not collected from a real
    # episode) -- deliberately proving the checker discriminates, mirroring
    # the equivalent negative test for the autofde-lab reference prototype.
    result = ConformanceChecker().check([Operation.DISCOVER, Operation.ACT])

    assert result.conformant is False
    assert len(result.deviations) == 2  # bad start AND bad transition
    reasons = [d.reason for d in result.deviations]
    assert any("must start with" in r for r in reasons)
    assert any("not a legal successor" in r for r in reasons)


# The three tests below close the gap the earlier three left open: those all
# use CubeCounterEnvironment(requires_authority=False) (the provider's
# default), so `GymAct.act()`'s authority check took the AUTHORITY_NOT_REQUIRED
# short-circuit and DenyAuthorityResolver/AllowListAuthorityResolver were
# never exercised in their required-and-gating path against this real,
# external gym -- only against the synthetic MemoryProvider (tests/test_core.py).
# These pass `config={"requires_authority": True}` to make the gate
# load-bearing, and assert on the real CUBE task's counter (via gym.observe,
# never a re-derived shadow value), not just on the accepted/refused flag.
#
# This proves the authority gate is load-bearing against a real external
# task. It does not, and is not claimed to, address counter-cube's own
# design as CUBE's deliberately simplest reference task (no Docker, no
# network, no subprocess, no multi-step planning, no adversarial conditions),
# say anything about infrastructure/cloud gyms, or make this 1-of-80 case
# representative of the other 79.


async def test_authority_refusal_does_not_change_real_cube_state() -> None:
    gym_instance = GymAct()  # default authority_resolver: fail-closed DenyAuthorityResolver
    gym_instance.register_provider(CubeCounterProvider())
    materialized = await gym_instance.materialize(
        MaterializationIntent(
            provider="cube-counter",
            config={"target": 3, "requires_authority": True},
        )
    )
    assert materialized.accepted is True
    episode_id = materialized.episode.episode_id

    result = await gym_instance.act(
        ActuationIntent(episode_id=episode_id, capability=INCREMENT_CAPABILITY)
    )

    assert result.accepted is False
    assert result.standing == Standing.REFUSED
    assert result.receipt.reason == "LIVE_AUTHORITY_REQUIRED"
    observation = await gym_instance.observe(episode_id)
    assert observation.state["counter"] == 0
    assert result.receipt.pre_state_digest == result.receipt.post_state_digest


async def test_authority_reference_without_admission_does_not_change_real_cube_state() -> None:
    gym_instance = GymAct()  # DenyAuthorityResolver refuses even a present authority_ref
    gym_instance.register_provider(CubeCounterProvider())
    materialized = await gym_instance.materialize(
        MaterializationIntent(
            provider="cube-counter",
            config={"target": 3, "requires_authority": True},
        )
    )
    episode_id = materialized.episode.episode_id

    result = await gym_instance.act(
        ActuationIntent(
            episode_id=episode_id,
            capability=INCREMENT_CAPABILITY,
            authority_ref=AUTHORITY,
        )
    )

    assert result.accepted is False
    assert result.standing == Standing.REFUSED
    assert result.receipt.reason == "AUTHORITY_NOT_ADMITTED"
    observation = await gym_instance.observe(episode_id)
    assert observation.state["counter"] == 0


async def test_admitted_authority_changes_real_cube_state() -> None:
    gym_instance = GymAct(authority_resolver=AllowListAuthorityResolver({AUTHORITY}))
    gym_instance.register_provider(CubeCounterProvider())
    materialized = await gym_instance.materialize(
        MaterializationIntent(
            provider="cube-counter",
            config={"target": 3, "requires_authority": True},
        )
    )
    episode_id = materialized.episode.episode_id

    refused = await gym_instance.act(
        ActuationIntent(
            episode_id=episode_id,
            capability=INCREMENT_CAPABILITY,
            authority_ref="urn:test:not-on-the-allowlist",
        )
    )
    assert refused.accepted is False
    assert refused.receipt.reason == "AUTHORITY_NOT_ADMITTED"
    assert (await gym_instance.observe(episode_id)).state["counter"] == 0

    admitted = await gym_instance.act(
        ActuationIntent(
            episode_id=episode_id,
            capability=INCREMENT_CAPABILITY,
            authority_ref=AUTHORITY,
        )
    )
    assert admitted.accepted is True
    assert admitted.standing == Standing.ALIVE
    assert admitted.receipt.authority_evidence_ref is not None
    observation = await gym_instance.observe(episode_id)
    assert observation.state["counter"] == 1
