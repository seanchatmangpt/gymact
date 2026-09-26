"""Canonical bounded policy/fault suites for survival experiments."""

from __future__ import annotations

from gymact.survival_campaign import SurvivalTraceTemplate
from gymact.survival_experiment import (
    InformationTopology,
    Machinery,
    SurvivalFactor,
    SurvivalPolicy,
    SurvivalStep,
    ToolPolicy,
)
from gymact.survival_faults import SurvivalFaultKind


def canonical_policy_suite() -> tuple[SurvivalPolicy, ...]:
    """Five machinery strata from general LLM ownership to formal/generated execution."""

    return (
        SurvivalPolicy(
            policy_id="llm-native",
            machinery=Machinery.LLM_NATIVE,
            information_topology=InformationTopology.ISOLATED,
            tool_policy=ToolPolicy.NONE,
        ),
        SurvivalPolicy(
            policy_id="llm-tools",
            machinery=Machinery.LLM_TOOLS,
            information_topology=InformationTopology.BROADCAST,
            tool_policy=ToolPolicy.MANDATORY,
        ),
        SurvivalPolicy(
            policy_id="selective-llm",
            machinery=Machinery.SELECTIVE_LLM,
            information_topology=InformationTopology.AUTHORITY_FILTERED,
            tool_policy=ToolPolicy.OPTIONAL,
        ),
        SurvivalPolicy(
            policy_id="planner-llm-residue",
            machinery=Machinery.PLANNER_LLM_RESIDUE,
            information_topology=InformationTopology.BLACKBOARD,
            tool_policy=ToolPolicy.OPTIONAL,
        ),
        SurvivalPolicy(
            policy_id="formal-generated",
            machinery=Machinery.FORMAL_GENERATED,
            information_topology=InformationTopology.RECEIPT_ONLY,
            tool_policy=ToolPolicy.OPTIONAL,
        ),
    )


def canonical_fault_suite() -> tuple[SurvivalFactor, ...]:
    """Reversible perturbations that exercise authority, transport, and evidence edges."""

    return (
        SurvivalFactor(
            name="authority",
            levels=("full", "filtered", "expired"),
        ),
        SurvivalFactor(
            name="transport",
            levels=("stable", "lossy", "reordered"),
        ),
        SurvivalFactor(
            name="evidence",
            levels=("complete", "delayed", "missing"),
        ),
        SurvivalFactor(
            name="terminal_signal",
            levels=("exact", "stale", "false_positive"),
        ),
    )




def canonical_fault_kinds() -> tuple[SurvivalFaultKind, ...]:
    """Every typed observational fault currently supported by the survival court."""

    return (
        SurvivalFaultKind.WRONG_SUBJECT,
        SurvivalFaultKind.AUTHORITY_DROP,
        SurvivalFaultKind.ADMISSION_DROP,
        SurvivalFaultKind.RECEIPT_DROP,
        SurvivalFaultKind.PREMATURE_TERMINAL,
        SurvivalFaultKind.TOOL_BLACKOUT,
        SurvivalFaultKind.REPLAY_CORRUPTION,
        SurvivalFaultKind.LLM_TOKEN_BURST,
    )


def canonical_trace_template(horizon: int) -> SurvivalTraceTemplate:
    """A deterministic synthetic process skeleton for qualification campaigns."""

    if isinstance(horizon, bool) or not isinstance(horizon, int) or horizon < 3:
        raise ValueError("SURVIVAL_CANONICAL_TEMPLATE_HORIZON_MIN_3")
    return SurvivalTraceTemplate(
        template_id=f"canonical:observe-verify-do:h{horizon}",
        steps=(
            SurvivalStep(step=1, phase="OBSERVE", tool_invoked=True),
            SurvivalStep(step=horizon - 1, phase="VERIFY"),
            SurvivalStep(
                step=horizon,
                phase="DO",
                exact_subject=True,
                authorized=True,
                admitted=True,
                receipt_id="synthetic:baseline-receipt",
                terminal_ready=True,
                replay_verified=True,
            ),
        ),
    )


__all__ = [
    "canonical_fault_kinds",
    "canonical_fault_suite",
    "canonical_policy_suite",
    "canonical_trace_template",
]
