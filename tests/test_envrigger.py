from __future__ import annotations

from dataclasses import replace

import pytest

from gymact.authority import AllowListAuthorityResolver
from gymact.envharness import HarnessAction, HarnessSession, HarnessSpec, TaskSpec
from gymact.envrigger import EnvRigger, EnvRiggerConfig, LoopGuardSynthesizer
from gymact.kernel import GymAct
from gymact.models import Standing
from gymact.providers import MemoryProvider

AUTHORITY = "urn:test:envrigger:authority"
INCREMENT = "urn:gymact:memory:capability:increment"


class IncrementUntilSolvedPolicy:
    def __call__(self, observation, capabilities):  # type: ignore[no-untyped-def]
        del capabilities
        if observation.get("count", 0) >= 2:
            return None
        return HarnessAction(capability=INCREMENT, payload={"key": "count"})


class IdentitySynthesizer:
    """Concrete data-only writer used to prove fresh Validate execution."""

    def propose(  # type: ignore[no-untyped-def]
        self, *, task, diagnosis, rollouts, revision, previous
    ):
        del task, diagnosis, rollouts
        return replace(previous, identifier=f"urn:test:candidate:{revision}")


class AlwaysIncrementPolicy:
    def __call__(self, observation, capabilities):  # type: ignore[no-untyped-def]
        del observation, capabilities
        return HarnessAction(capability=INCREMENT, payload={"key": "count"})


def build_runtime() -> GymAct:
    gym = GymAct(authority_resolver=AllowListAuthorityResolver({AUTHORITY}))
    gym.register_provider(MemoryProvider())
    return gym


@pytest.mark.asyncio
async def test_envrigger_runs_observe_diagnose_write_validate_on_fresh_real_episodes() -> None:
    gym = build_runtime()
    sessions_created = 0

    def session_factory(task: TaskSpec) -> HarnessSession:
        nonlocal sessions_created
        sessions_created += 1
        return HarnessSession(gym, task, authority_ref=AUTHORITY)

    task = TaskSpec(
        provider="memory",
        config={"initial": {"count": 0}, "requires_authority": True},
        goal={"count": 2},
        harness=HarnessSpec(identifier="urn:test:baseline"),
    )
    rigger = EnvRigger(
        session_factory=session_factory,
        policy=IncrementUntilSolvedPolicy(),
        synthesizer=IdentitySynthesizer(),
        config=EnvRiggerConfig(
            baseline_rollouts=2,
            validation_rollouts=3,
            max_steps=4,
            revision_budget=2,
            min_solvable_success_rate=0.5,
            max_easy_success_rate=1.0,
        ),
    )

    result = await rigger.run(task)

    assert result.standing == Standing.ALIVE
    assert result.accepted_harness is not None
    assert result.accepted_harness.identifier == "urn:test:candidate:1"
    assert len(result.baseline) == 2
    assert len(result.evaluations) == 1
    assert result.evaluations[0].validation.fresh_rollouts is True
    assert result.evaluations[0].validation.success_rate == 1.0
    # 2 Observe rollouts + 3 fresh Validate rollouts. No validation episode is reused.
    assert sessions_created == 5


@pytest.mark.asyncio
async def test_default_writer_synthesizes_loop_guard_without_crowning_unsolvable_candidate() -> (
    None
):
    gym = build_runtime()

    def session_factory(task: TaskSpec) -> HarnessSession:
        return HarnessSession(gym, task, authority_ref=AUTHORITY)

    task = TaskSpec(
        provider="memory",
        config={"initial": {"count": 0}, "requires_authority": True},
        # Policy increments forever while goal requires an unrelated key.
        goal={"done": True},
        harness=HarnessSpec(identifier="urn:test:looping-baseline"),
    )
    rigger = EnvRigger(
        session_factory=session_factory,
        policy=AlwaysIncrementPolicy(),
        synthesizer=LoopGuardSynthesizer(),
        config=EnvRiggerConfig(
            baseline_rollouts=1,
            validation_rollouts=1,
            max_steps=5,
            revision_budget=1,
            min_solvable_success_rate=0.5,
            max_easy_success_rate=1.0,
        ),
    )

    result = await rigger.run(task)

    assert result.baseline_diagnosis.max_consecutive_repeat >= 3
    assert "ACTION_LOOP_OBSERVED" in result.baseline_diagnosis.signal
    assert result.standing == Standing.REFUSED
    assert result.accepted_harness is None
    assert len(result.evaluations) == 1
    assert result.evaluations[0].validation.success_rate == 0.0
    assert result.evaluations[0].reason == "CANDIDATE_NOT_SOLVABLE_ENOUGH"
    assert result.reason == "ENVRIGGER_REVISION_BUDGET_EXHAUSTED"
