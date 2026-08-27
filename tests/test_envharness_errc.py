from __future__ import annotations

from dataclasses import replace

import pytest

from gymact.authority import AllowListAuthorityResolver
from gymact.envharness import (
    Contract,
    ContractRule,
    HarnessAction,
    HarnessSession,
    HarnessSpec,
    Stage,
    TaskSpec,
)
from gymact.envrigger import EnvRigger, EnvRiggerConfig
from gymact.kernel import GymAct
from gymact.models import AuthorityDecision, Operation, Standing
from gymact.providers import MemoryProvider

AUTHORITY = "urn:test:envharness:errc:authority"
SET = "urn:gymact:memory:capability:set"
INCREMENT = "urn:gymact:memory:capability:increment"
UNKNOWN = "urn:test:capability:unknown"


def runtime(*, authorized: bool = True) -> GymAct:
    resolver = AllowListAuthorityResolver({AUTHORITY}) if authorized else None
    gym = GymAct(authority_resolver=resolver) if resolver is not None else GymAct()
    gym.register_provider(MemoryProvider())
    return gym


class DenyTeardownAuthorityResolver:
    async def authorize(self, request):  # type: ignore[no-untyped-def]
        if request.authority_ref != AUTHORITY:
            return AuthorityDecision(admitted=False, reason="AUTHORITY_NOT_ADMITTED")
        if request.operation is Operation.TEARDOWN:
            return AuthorityDecision(admitted=False, reason="TEARDOWN_NOT_ADMITTED")
        return AuthorityDecision(
            admitted=True,
            reason="AUTHORITY_ADMITTED",
            evidence_ref=f"urn:gymact:authority-decision:{AUTHORITY}",
        )


def runtime_with_refused_teardown() -> GymAct:
    gym = GymAct(authority_resolver=DenyTeardownAuthorityResolver())
    gym.register_provider(MemoryProvider())
    return gym


def test_harness_identity_is_content_addressed_not_execution_randomness() -> None:
    first = HarnessSpec(
        stages=(Stage(actions=(HarnessAction(capability=SET, payload={"key": "x", "value": 1}),)),)
    )
    second = HarnessSpec(
        stages=(Stage(actions=(HarnessAction(capability=SET, payload={"key": "x", "value": 1}),)),)
    )

    assert first.identifier == second.identifier
    assert first.semantic_digest == second.semantic_digest
    assert first.stages[0].actions[0].idempotency_key != second.stages[0].actions[0].idempotency_key


@pytest.mark.asyncio
async def test_stage_preflight_eliminates_partial_actuation_for_static_invalidity() -> None:
    gym = runtime()
    task = TaskSpec(
        provider="memory",
        config={"initial": {"count": 0}, "requires_authority": True},
        harness=HarnessSpec(
            stages=(
                Stage(
                    actions=(
                        HarnessAction(capability=SET, payload={"key": "count", "value": 1}),
                        HarnessAction(capability=UNKNOWN),
                    )
                ),
            )
        ),
    )
    session = HarnessSession(gym, task, authority_ref=AUTHORITY)

    reset = await session.reset()

    assert reset.accepted is False
    assert reset.standing == Standing.UNSUPPORTED
    assert reset.reason == "STAGE_CAPABILITY_UNSUPPORTED"
    assert reset.admission is not None
    assert reset.admission.checked_stage_actions == 2
    assert reset.stage_results == ()
    assert reset.cleanup_receipt is not None
    assert reset.cleanup_receipt.operation == Operation.TEARDOWN
    assert reset.cleanup_receipt.standing == Standing.ALIVE
    assert session.episode_id is None
    with pytest.raises(RuntimeError, match="ENVHARNESS_NOT_RESET"):
        await session.raw_observe()
    receipts = gym.episode_receipts(reset.materialization.episode.episode_id)
    assert all(receipt.operation != Operation.ACT for receipt in receipts)


@pytest.mark.asyncio
async def test_stage_preflight_cleanup_refusal_is_fail_closed_and_recoverable() -> None:
    gym = runtime_with_refused_teardown()
    task = TaskSpec(
        provider="memory",
        config={"initial": {"count": 0}, "requires_authority": True},
        harness=HarnessSpec(
            stages=(Stage(actions=(HarnessAction(capability=UNKNOWN),)),)
        ),
    )
    session = HarnessSession(gym, task, authority_ref=AUTHORITY)

    reset = await session.reset()

    assert reset.accepted is False
    assert reset.standing == Standing.REFUSED
    assert reset.reason == "HARNESS_ADMISSION_CLEANUP_FAILED:STAGE_CAPABILITY_UNSUPPORTED"
    assert reset.admission is not None
    assert reset.admission.standing == Standing.UNSUPPORTED
    assert reset.cleanup_receipt is not None
    assert reset.cleanup_receipt.operation == Operation.TEARDOWN
    assert reset.cleanup_receipt.standing == Standing.REFUSED
    assert session.episode_id == reset.materialization.episode.episode_id
    assert (await session.raw_observe()).state == {"count": 0}
    receipts = gym.episode_receipts(session.episode_id)
    assert all(receipt.operation != Operation.ACT for receipt in receipts)


@pytest.mark.asyncio
async def test_contract_replace_payload_eliminates_stale_source_arguments() -> None:
    gym = runtime()
    task = TaskSpec(
        provider="memory",
        config={"initial": {"count": 0}, "requires_authority": True},
        harness=HarnessSpec(
            contracts=(
                Contract(
                    rules=(
                        ContractRule(
                            capability=SET,
                            effect="rewrite",
                            rewrite_capability=INCREMENT,
                            payload_mode="replace",
                            payload_overrides={"key": "count", "amount": 2},
                            reason="ERRC_REWRITE",
                        ),
                    )
                ),
            )
        ),
    )
    session = HarnessSession(gym, task, authority_ref=AUTHORITY)
    assert (await session.reset()).accepted

    decision = await session.admit(
        HarnessAction(capability=SET, payload={"key": "count", "value": 999, "stale": True})
    )

    assert decision.admitted is True
    assert decision.action.capability == INCREMENT
    assert decision.action.copied_payload() == {"key": "count", "amount": 2}


@pytest.mark.asyncio
async def test_step_postcondition_failure_rolls_back_receipted_world_change() -> None:
    gym = runtime()
    task = TaskSpec(
        provider="memory",
        config={"initial": {"count": 0}, "requires_authority": True},
    )
    session = HarnessSession(gym, task, authority_ref=AUTHORITY)
    assert (await session.reset()).accepted

    result = await session.step(
        HarnessAction(
            capability=SET,
            payload={"key": "count", "value": 1},
            expected_after={"count": 999},
        )
    )

    assert result.accepted is False
    assert result.standing == Standing.REFUSED
    assert result.reason == "STEP_POSTCONDITION_FAILED"
    assert result.actuation is not None
    assert result.actuation.receipt.operation == Operation.ACT
    assert result.postcondition_verification is not None
    assert result.postcondition_verification.passed is False
    assert result.rollback_receipt is not None
    assert result.rollback_receipt.operation == Operation.RESTORE
    assert result.rollback_receipt.standing == Standing.ALIVE
    assert session.history == ()
    assert (await session.raw_observe()).state == {"count": 0}


class CountingSynthesizer:
    def __init__(self) -> None:
        self.calls = 0

    def propose(self, **kwargs):  # type: ignore[no-untyped-def]
        self.calls += 1
        previous = kwargs["previous"]
        return replace(previous, identifier=f"{previous.identifier}:candidate")


class NoopPolicy:
    def __call__(self, observation, capabilities):  # type: ignore[no-untyped-def]
        del observation, capabilities
        return None


@pytest.mark.asyncio
async def test_envrigger_does_not_synthesize_around_failed_reset_authority() -> None:
    gym = runtime(authorized=False)
    synthesizer = CountingSynthesizer()

    def session_factory(task: TaskSpec) -> HarnessSession:
        return HarnessSession(gym, task)

    task = TaskSpec(
        provider="memory",
        config={"initial": {"count": 0}, "requires_authority": True},
        harness=HarnessSpec(
            stages=(
                Stage(
                    actions=(HarnessAction(capability=SET, payload={"key": "count", "value": 1}),)
                ),
            )
        ),
    )
    rigger = EnvRigger(
        session_factory=session_factory,
        policy=NoopPolicy(),
        synthesizer=synthesizer,
        config=EnvRiggerConfig(baseline_rollouts=1, validation_rollouts=1),
    )

    result = await rigger.run(task)

    assert result.standing == Standing.REFUSED
    assert result.reason == "BASELINE_LIFECYCLE_NOT_ADMITTED"
    assert result.baseline_diagnosis.lifecycle_failures == 1
    assert synthesizer.calls == 0
    # Cleanup is attempted through the same fail-closed authority boundary; it
    # must not manufacture ALIVE by bypassing the authority that refused Stage.
    assert result.baseline[0].teardown_standing == Standing.REFUSED


@pytest.mark.asyncio
async def test_envrigger_refuses_identifier_only_noop_candidate() -> None:
    gym = runtime()
    synthesizer = CountingSynthesizer()

    def session_factory(task: TaskSpec) -> HarnessSession:
        return HarnessSession(gym, task, authority_ref=AUTHORITY)

    task = TaskSpec(
        provider="memory",
        config={"initial": {"done": False}, "requires_authority": True},
        goal={"done": False},
    )
    rigger = EnvRigger(
        session_factory=session_factory,
        policy=NoopPolicy(),
        synthesizer=synthesizer,
        config=EnvRiggerConfig(
            baseline_rollouts=1,
            validation_rollouts=1,
            min_solvable_success_rate=0.0,
            max_easy_success_rate=1.0,
        ),
    )

    result = await rigger.run(task)

    assert synthesizer.calls == 1
    assert result.standing == Standing.UNSUPPORTED
    assert result.reason == "SYNTHESIZER_PRODUCED_NO_SEMANTIC_CHANGE"
    assert result.evaluations == ()
