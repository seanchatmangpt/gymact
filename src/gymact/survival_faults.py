"""Deterministic observational fault plans for survival experiments.

Fault plans are experiment inputs, not permissions. They transform an observed
or simulated SurvivalStep sequence into another bounded sequence so the same
survival court can falsify resilience claims. No fault performs external I/O,
executes a tool, or widens authority.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import Field, model_validator

from gymact.evidence import digest
from gymact.models import FrozenModel
from gymact.survival_experiment import SurvivalStep


class SurvivalFaultKind(StrEnum):
    WRONG_SUBJECT = "wrong_subject"
    AUTHORITY_DROP = "authority_drop"
    ADMISSION_DROP = "admission_drop"
    RECEIPT_DROP = "receipt_drop"
    PREMATURE_TERMINAL = "premature_terminal"
    TOOL_BLACKOUT = "tool_blackout"
    REPLAY_CORRUPTION = "replay_corruption"
    LLM_TOKEN_BURST = "llm_token_burst"


class SurvivalFault(FrozenModel):
    kind: SurvivalFaultKind
    target_step: int = Field(ge=1)
    magnitude: int = Field(ge=0, default=0)

    @model_validator(mode="after")
    def validate_magnitude(self) -> "SurvivalFault":
        if self.kind is SurvivalFaultKind.LLM_TOKEN_BURST and self.magnitude < 1:
            raise ValueError("SURVIVAL_LLM_BURST_MAGNITUDE_REQUIRED")
        if self.kind is not SurvivalFaultKind.LLM_TOKEN_BURST and self.magnitude != 0:
            raise ValueError("SURVIVAL_FAULT_MAGNITUDE_NOT_APPLICABLE")
        return self


class SurvivalFaultPlan(FrozenModel):
    plan_id: str = Field(min_length=1)
    faults: tuple[SurvivalFault, ...]
    authority: Literal["none"] = "none"
    actuation_performed: Literal[False] = False

    @model_validator(mode="after")
    def validate_unique_targets(self) -> "SurvivalFaultPlan":
        keys = [(fault.target_step, fault.kind) for fault in self.faults]
        if len(keys) != len(set(keys)):
            raise ValueError("SURVIVAL_FAULT_DUPLICATE")
        return self

    @property
    def plan_digest(self) -> str:
        return digest(self.model_dump(mode="json"))


class SurvivalFaultApplication(FrozenModel):
    plan_digest: str = Field(min_length=64, max_length=64)
    input_digest: str = Field(min_length=64, max_length=64)
    output_digest: str = Field(min_length=64, max_length=64)
    touched_steps: tuple[int, ...]
    authority: Literal["none"] = "none"
    actuation_performed: Literal[False] = False


def _require_do(step: SurvivalStep, fault: SurvivalFault) -> None:
    if step.phase != "DO":
        raise ValueError(
            f"SURVIVAL_FAULT_REQUIRES_DO:{fault.kind.value}:step={fault.target_step}"
        )


def _mutate(step: SurvivalStep, fault: SurvivalFault) -> SurvivalStep:
    update: dict[str, object] = {}
    if fault.kind is SurvivalFaultKind.WRONG_SUBJECT:
        _require_do(step, fault)
        update["exact_subject"] = False
    elif fault.kind is SurvivalFaultKind.AUTHORITY_DROP:
        _require_do(step, fault)
        update["authorized"] = False
    elif fault.kind is SurvivalFaultKind.ADMISSION_DROP:
        _require_do(step, fault)
        update["admitted"] = False
    elif fault.kind is SurvivalFaultKind.RECEIPT_DROP:
        _require_do(step, fault)
        update["receipt_id"] = None
        update["replay_verified"] = False
    elif fault.kind is SurvivalFaultKind.PREMATURE_TERMINAL:
        _require_do(step, fault)
        update["terminal_ready"] = False
    elif fault.kind is SurvivalFaultKind.TOOL_BLACKOUT:
        update["tool_invoked"] = False
    elif fault.kind is SurvivalFaultKind.REPLAY_CORRUPTION:
        _require_do(step, fault)
        update["replay_verified"] = False
    elif fault.kind is SurvivalFaultKind.LLM_TOKEN_BURST:
        update["llm_tokens"] = step.llm_tokens + fault.magnitude
    else:
        raise AssertionError(f"unhandled survival fault {fault.kind}")
    return step.model_copy(update=update)


def apply_survival_fault_plan(
    steps: tuple[SurvivalStep, ...],
    plan: SurvivalFaultPlan,
) -> tuple[tuple[SurvivalStep, ...], SurvivalFaultApplication]:
    """Apply a deterministic fault plan to an in-memory step trace."""

    by_step = {step.step: step for step in steps}
    if len(by_step) != len(steps):
        raise ValueError("SURVIVAL_FAULT_INPUT_STEP_DUPLICATE")

    touched: set[int] = set()
    for fault in plan.faults:
        if fault.target_step not in by_step:
            raise ValueError(f"SURVIVAL_FAULT_TARGET_MISSING:{fault.target_step}")
        by_step[fault.target_step] = _mutate(by_step[fault.target_step], fault)
        touched.add(fault.target_step)

    output = tuple(by_step[step] for step in sorted(by_step))
    input_payload = [step.model_dump(mode="json") for step in steps]
    output_payload = [step.model_dump(mode="json") for step in output]
    receipt = SurvivalFaultApplication(
        plan_digest=plan.plan_digest,
        input_digest=digest(input_payload),
        output_digest=digest(output_payload),
        touched_steps=tuple(sorted(touched)),
    )
    return output, receipt


def manufacture_single_fault_plans(
    steps: tuple[SurvivalStep, ...],
    kinds: tuple[SurvivalFaultKind, ...],
    *,
    llm_burst_magnitude: int = 100,
) -> tuple[SurvivalFaultPlan, ...]:
    """Manufacture every lawful single-fault perturbation over a trace."""

    plans: list[SurvivalFaultPlan] = []
    do_only = {
        SurvivalFaultKind.WRONG_SUBJECT,
        SurvivalFaultKind.AUTHORITY_DROP,
        SurvivalFaultKind.ADMISSION_DROP,
        SurvivalFaultKind.RECEIPT_DROP,
        SurvivalFaultKind.PREMATURE_TERMINAL,
        SurvivalFaultKind.REPLAY_CORRUPTION,
    }
    for step in steps:
        for kind in kinds:
            if kind in do_only and step.phase != "DO":
                continue
            magnitude = llm_burst_magnitude if kind is SurvivalFaultKind.LLM_TOKEN_BURST else 0
            plans.append(
                SurvivalFaultPlan(
                    plan_id=f"fault:{kind.value}:step-{step.step}",
                    faults=(
                        SurvivalFault(
                            kind=kind,
                            target_step=step.step,
                            magnitude=magnitude,
                        ),
                    ),
                )
            )
    return tuple(plans)


__all__ = [
    "SurvivalFault",
    "SurvivalFaultApplication",
    "SurvivalFaultKind",
    "SurvivalFaultPlan",
    "apply_survival_fault_plan",
    "manufacture_single_fault_plans",
]
