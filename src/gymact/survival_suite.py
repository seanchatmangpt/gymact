"""Canonical bounded policy/fault suites for survival experiments."""

from __future__ import annotations

from gymact.survival_experiment import (
    InformationTopology,
    Machinery,
    SurvivalFactor,
    SurvivalPolicy,
    ToolPolicy,
)


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


__all__ = ["canonical_fault_suite", "canonical_policy_suite"]
