from __future__ import annotations

import pytest

from gymact.authority import AllowListAuthorityResolver
from gymact.envharness import (
    ChainSession,
    Contract,
    ContractRule,
    HarnessAction,
    HarnessSession,
    HarnessSpec,
    Stage,
    TaskSpec,
)
from gymact.kernel import GymAct
from gymact.models import Operation, Standing
from gymact.providers import MemoryProvider

AUTHORITY = "urn:test:envharness:authority"
SET = "urn:gymact:memory:capability:set"
DELETE = "urn:gymact:memory:capability:delete"
INCREMENT = "urn:gymact:memory:capability:increment"


def runtime(*, authorized: bool = True) -> GymAct:
    if authorized:
        result = GymAct(authority_resolver=AllowListAuthorityResolver({AUTHORITY}))
    else:
        result = GymAct()
    result.register_provider(MemoryProvider())
    return result


@pytest.mark.asyncio
async def test_stage_is_real_receipted_actuation_not_hidden_reset_mutation() -> None:
    gym = runtime()
    task = TaskSpec(
        provider="memory",
        config={"initial": {"count": 0}, "requires_authority": True},
        goal={"count": 2},
        harness=HarnessSpec(
            stages=(
                Stage(
                    actions=(
                        HarnessAction(
                            capability=INCREMENT,
                            payload={"key": "count", "amount": 2},
                            expected_after={"count": 2},
                        ),
                    )
                ),
            ),
        ),
    )
    session = HarnessSession(gym, task, authority_ref=AUTHORITY)

    reset = await session.reset()

    assert reset.accepted is True
    assert reset.standing == Standing.ALIVE
    assert len(reset.stage_results) == 1
    assert reset.stage_results[0].receipt.operation == Operation.ACT
    assert reset.stage_results[0].receipt.authority_ref == AUTHORITY
    assert reset.stage_results[0].receipt.authority_evidence_ref is not None
    assert len(reset.stage_verifications) == 1
    assert reset.stage_verifications[0].passed is True
    assert (await session.raw_observe()).state == {"count": 2}


@pytest.mark.asyncio
async def test_stage_failure_rolls_back_through_receipted_restore() -> None:
    gym = runtime()
    task = TaskSpec(
        provider="memory",
        config={"initial": {"count": 0}, "requires_authority": True},
        harness=HarnessSpec(
            stages=(
                Stage(
                    actions=(
                        HarnessAction(
                            capability=SET,
                            payload={"key": "count", "value": 1},
                            expected_after={"count": 999},
                        ),
                    )
                ),
            ),
        ),
    )
    session = HarnessSession(gym, task, authority_ref=AUTHORITY)

    reset = await session.reset()

    assert reset.accepted is False
    assert reset.reason == "STAGE_POSTCONDITION_FAILED"
    assert reset.rollback_receipt is not None
    assert reset.rollback_receipt.operation == Operation.RESTORE
    assert reset.rollback_receipt.standing == Standing.ALIVE
    assert (await session.raw_observe()).state == {"count": 0}


@pytest.mark.asyncio
async def test_stage_cannot_bypass_fail_closed_authority() -> None:
    gym = runtime(authorized=False)
    task = TaskSpec(
        provider="memory",
        config={"initial": {"safe": False}, "requires_authority": True},
        harness=HarnessSpec(
            stages=(
                Stage(
                    actions=(
                        HarnessAction(capability=SET, payload={"key": "safe", "value": True}),
                    )
                ),
            ),
        ),
    )
    session = HarnessSession(gym, task)

    reset = await session.reset()

    assert reset.accepted is False
    assert reset.standing == Standing.REFUSED
    assert reset.stage_results[0].receipt.reason == "LIVE_AUTHORITY_REQUIRED"
    assert (await session.raw_observe()).state == {"safe": False}


@pytest.mark.asyncio
async def test_contract_denial_is_typed_evidenced_and_has_zero_world_change() -> None:
    gym = runtime()
    task = TaskSpec(
        provider="memory",
        config={"initial": {"keep": 7}, "requires_authority": True},
        harness=HarnessSpec(
            contracts=(
                Contract(
                    rules=(
                        ContractRule(
                            capability=DELETE,
                            effect="deny",
                            reason="CONTRACT_FORBIDS_DELETE",
                            feedback="Deletion is unavailable in this harness.",
                        ),
                    ),
                ),
            ),
        ),
    )
    session = HarnessSession(gym, task, authority_ref=AUTHORITY)
    reset = await session.reset()
    assert reset.accepted
    before_receipts = len(gym.episode_receipts(session.episode_id or ""))

    result = await session.step(HarnessAction(capability=DELETE, payload={"key": "keep"}))

    assert result.accepted is False
    assert result.standing == Standing.REFUSED
    assert result.reason == "CONTRACT_FORBIDS_DELETE"
    assert result.contract_decision is not None
    assert result.contract_decision.evidence_digest
    assert (await session.raw_observe()).state == {"keep": 7}
    # Contract denial is pre-actuation: no fake ACT Receipt is minted for an operation
    # that never crossed the GymAct consequence boundary.
    assert len(gym.episode_receipts(session.episode_id or "")) == before_receipts


@pytest.mark.asyncio
async def test_contract_rewrite_reenters_authority_on_exact_transformed_capability() -> None:
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
                            payload_overrides={"amount": 2},
                            reason="REWRITE_SET_TO_INCREMENT",
                        ),
                    ),
                ),
            ),
        ),
    )
    session = HarnessSession(gym, task, authority_ref=AUTHORITY)
    assert (await session.reset()).accepted

    result = await session.step(
        HarnessAction(capability=SET, payload={"key": "count", "value": 500})
    )

    assert result.accepted is True
    assert result.action.capability == INCREMENT
    assert result.actuation is not None
    assert result.actuation.receipt.capability_ref == INCREMENT
    assert result.actuation.receipt.authority_evidence_ref is not None
    assert (await session.raw_observe()).state == {"count": 2}


@pytest.mark.asyncio
async def test_contract_observation_projection_never_changes_original_verifier() -> None:
    gym = runtime()
    task = TaskSpec(
        provider="memory",
        config={"initial": {"public": 1, "secret": 7}, "requires_authority": True},
        goal={"secret": 7},
        harness=HarnessSpec(
            contracts=(Contract(hide_observation_keys=frozenset({"secret"})),),
        ),
    )
    session = HarnessSession(gym, task, authority_ref=AUTHORITY)
    assert (await session.reset()).accepted

    projected = await session.observe()
    verified = await session.verify()

    assert projected == {"public": 1}
    assert verified.passed is True
    assert verified.observed["secret"] == 7


@pytest.mark.asyncio
async def test_contract_loop_guard_blocks_third_consecutive_action() -> None:
    gym = runtime()
    task = TaskSpec(
        provider="memory",
        config={"initial": {"count": 0}, "requires_authority": True},
        harness=HarnessSpec(
            contracts=(
                Contract(
                    rules=(
                        ContractRule(
                            capability=INCREMENT,
                            effect="deny",
                            max_consecutive=2,
                            reason="LOOP_GUARD",
                        ),
                    ),
                ),
            ),
        ),
    )
    session = HarnessSession(gym, task, authority_ref=AUTHORITY)
    assert (await session.reset()).accepted

    first = await session.step(HarnessAction(capability=INCREMENT, payload={"key": "count"}))
    second = await session.step(HarnessAction(capability=INCREMENT, payload={"key": "count"}))
    third = await session.step(HarnessAction(capability=INCREMENT, payload={"key": "count"}))

    assert first.accepted and second.accepted
    assert third.accepted is False
    assert third.reason == "LOOP_GUARD"
    assert (await session.raw_observe()).state == {"count": 2}


@pytest.mark.asyncio
async def test_chain_is_serial_and_conjoins_each_original_leg_verifier() -> None:
    gym = runtime()
    tasks = (
        TaskSpec(
            provider="memory",
            config={"initial": {"leg": 0}, "requires_authority": True},
            goal={"leg": 1},
        ),
        TaskSpec(
            provider="memory",
            config={"initial": {"leg": 10}, "requires_authority": True},
            goal={"leg": 11},
        ),
    )
    chain = ChainSession(gym, tasks, authority_ref=AUTHORITY)
    assert (await chain.reset()).accepted

    await chain.step(HarnessAction(capability=INCREMENT, payload={"key": "leg"}))
    first = await chain.advance()
    assert first.accepted is True
    assert first.complete is False
    assert first.next_reset is not None and first.next_reset.accepted

    await chain.step(HarnessAction(capability=INCREMENT, payload={"key": "leg"}))
    second = await chain.advance()

    assert second.accepted is True
    assert second.complete is True
    assert chain.complete is True
    assert len(chain.verifications) == 2
    assert all(item.passed for item in chain.verifications)
