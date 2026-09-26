from __future__ import annotations

import pytest
from pydantic import ValidationError

from gymact.survival_experiment import SurvivalStep
from gymact.survival_faults import (
    SurvivalFault,
    SurvivalFaultKind,
    SurvivalFaultPlan,
    apply_survival_fault_plan,
    manufacture_single_fault_plans,
)


def baseline() -> tuple[SurvivalStep, ...]:
    return (
        SurvivalStep(step=1, phase="OBSERVE", tool_invoked=True, llm_tokens=3),
        SurvivalStep(step=2, phase="VERIFY"),
        SurvivalStep(
            step=3,
            phase="DO",
            authorized=True,
            admitted=True,
            receipt_id="receipt:3",
            replay_verified=True,
            terminal_ready=True,
        ),
    )


@pytest.mark.parametrize(
    ("kind", "field", "expected"),
    [
        (SurvivalFaultKind.WRONG_SUBJECT, "exact_subject", False),
        (SurvivalFaultKind.AUTHORITY_DROP, "authorized", False),
        (SurvivalFaultKind.ADMISSION_DROP, "admitted", False),
        (SurvivalFaultKind.RECEIPT_DROP, "receipt_id", None),
        (SurvivalFaultKind.PREMATURE_TERMINAL, "terminal_ready", False),
        (SurvivalFaultKind.REPLAY_CORRUPTION, "replay_verified", False),
    ],
)
def test_do_faults_mutate_only_the_targeted_observation(kind, field, expected) -> None:
    steps = baseline()
    plan = SurvivalFaultPlan(
        plan_id=f"plan:{kind.value}",
        faults=(SurvivalFault(kind=kind, target_step=3),),
    )

    mutated, receipt = apply_survival_fault_plan(steps, plan)

    assert getattr(mutated[2], field) == expected
    assert mutated[0] == steps[0]
    assert mutated[1] == steps[1]
    assert receipt.touched_steps == (3,)
    assert receipt.authority == "none"
    assert receipt.actuation_performed is False
    assert receipt.input_digest != receipt.output_digest


def test_receipt_drop_also_invalidates_replay_observation() -> None:
    mutated, _ = apply_survival_fault_plan(
        baseline(),
        SurvivalFaultPlan(
            plan_id="receipt-drop",
            faults=(
                SurvivalFault(
                    kind=SurvivalFaultKind.RECEIPT_DROP,
                    target_step=3,
                ),
            ),
        ),
    )

    assert mutated[2].receipt_id is None
    assert mutated[2].replay_verified is False


def test_llm_burst_is_additive_and_requires_positive_magnitude() -> None:
    mutated, _ = apply_survival_fault_plan(
        baseline(),
        SurvivalFaultPlan(
            plan_id="llm-burst",
            faults=(
                SurvivalFault(
                    kind=SurvivalFaultKind.LLM_TOKEN_BURST,
                    target_step=1,
                    magnitude=97,
                ),
            ),
        ),
    )

    assert mutated[0].llm_tokens == 100

    with pytest.raises(ValidationError, match="SURVIVAL_LLM_BURST_MAGNITUDE_REQUIRED"):
        SurvivalFault(
            kind=SurvivalFaultKind.LLM_TOKEN_BURST,
            target_step=1,
        )


def test_do_fault_refuses_non_do_target() -> None:
    with pytest.raises(ValueError, match="SURVIVAL_FAULT_REQUIRES_DO"):
        apply_survival_fault_plan(
            baseline(),
            SurvivalFaultPlan(
                plan_id="bad-target",
                faults=(
                    SurvivalFault(
                        kind=SurvivalFaultKind.AUTHORITY_DROP,
                        target_step=1,
                    ),
                ),
            ),
        )


def test_fault_plan_refuses_missing_target_or_duplicate_fault() -> None:
    with pytest.raises(ValueError, match="SURVIVAL_FAULT_TARGET_MISSING"):
        apply_survival_fault_plan(
            baseline(),
            SurvivalFaultPlan(
                plan_id="missing",
                faults=(
                    SurvivalFault(
                        kind=SurvivalFaultKind.TOOL_BLACKOUT,
                        target_step=99,
                    ),
                ),
            ),
        )

    with pytest.raises(ValidationError, match="SURVIVAL_FAULT_DUPLICATE"):
        SurvivalFaultPlan(
            plan_id="duplicate",
            faults=(
                SurvivalFault(kind=SurvivalFaultKind.TOOL_BLACKOUT, target_step=1),
                SurvivalFault(kind=SurvivalFaultKind.TOOL_BLACKOUT, target_step=1),
            ),
        )


def test_fault_manufacturer_preserves_only_lawful_single_fault_locations() -> None:
    plans = manufacture_single_fault_plans(
        baseline(),
        (
            SurvivalFaultKind.AUTHORITY_DROP,
            SurvivalFaultKind.TOOL_BLACKOUT,
            SurvivalFaultKind.LLM_TOKEN_BURST,
        ),
        llm_burst_magnitude=50,
    )

    authority_plans = [
        plan for plan in plans if plan.faults[0].kind is SurvivalFaultKind.AUTHORITY_DROP
    ]
    tool_plans = [
        plan for plan in plans if plan.faults[0].kind is SurvivalFaultKind.TOOL_BLACKOUT
    ]
    burst_plans = [
        plan for plan in plans if plan.faults[0].kind is SurvivalFaultKind.LLM_TOKEN_BURST
    ]

    assert [plan.faults[0].target_step for plan in authority_plans] == [3]
    assert [plan.faults[0].target_step for plan in tool_plans] == [1, 2, 3]
    assert [plan.faults[0].target_step for plan in burst_plans] == [1, 2, 3]
    assert all(plan.faults[0].magnitude == 50 for plan in burst_plans)
