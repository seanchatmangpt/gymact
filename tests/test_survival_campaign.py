from __future__ import annotations

import pytest
from pydantic import ValidationError

from gymact.survival_campaign import (
    SurvivalCampaignSpec,
    SurvivalTraceTemplate,
    manufacture_survival_campaign,
)
from gymact.survival_experiment import (
    Machinery,
    SurvivalExperiment,
    SurvivalPolicy,
    SurvivalScenario,
    SurvivalStep,
)
from gymact.survival_faults import SurvivalFaultKind


def experiment(*, horizon: int = 4) -> SurvivalExperiment:
    return SurvivalExperiment(
        experiment_id="campaign-experiment",
        scenarios=(
            SurvivalScenario(
                scenario_id="world",
                subject="git:seanchatmangpt/gymact@0123456789abcdef",
                workload_id="sha256:campaign-workload",
                horizon=horizon,
                terminal_predicate_ref="urn:predicate:done",
            ),
        ),
        policies=(
            SurvivalPolicy(policy_id="llm", machinery=Machinery.LLM_NATIVE),
            SurvivalPolicy(
                policy_id="formal",
                machinery=Machinery.FORMAL_GENERATED,
            ),
        ),
    )


def template() -> SurvivalTraceTemplate:
    return SurvivalTraceTemplate(
        template_id="template:one-do",
        steps=(
            SurvivalStep(step=1, phase="OBSERVE", tool_invoked=True, llm_tokens=3),
            SurvivalStep(step=2, phase="VERIFY"),
            SurvivalStep(
                step=4,
                phase="DO",
                authorized=True,
                admitted=True,
                receipt_id="receipt:4",
                replay_verified=True,
                terminal_ready=True,
            ),
        ),
    )


def test_campaign_cross_products_run_cases_with_every_lawful_fault_plan() -> None:
    spec = SurvivalCampaignSpec(
        campaign_id="campaign:v26.9.25",
        experiment=experiment(),
        template=template(),
        fault_kinds=(
            SurvivalFaultKind.AUTHORITY_DROP,
            SurvivalFaultKind.TOOL_BLACKOUT,
            SurvivalFaultKind.LLM_TOKEN_BURST,
        ),
        include_baseline=True,
        llm_burst_magnitude=50,
    )

    campaign = manufacture_survival_campaign(spec)

    # per run case: baseline + 1 DO-only authority fault + 3 tool + 3 LLM burst
    assert spec.variants_per_run_case == 8
    assert spec.campaign_case_count == 16
    assert len(campaign.cases) == 16
    assert len({case.campaign_case_id for case in campaign.cases}) == 16
    assert all(case.synthetic is True for case in campaign.cases)
    assert all(case.authority == "none" for case in campaign.cases)
    assert all(case.actuation_performed is False for case in campaign.cases)


def test_campaign_documents_preserve_fault_identity_without_changing_policy_identity() -> None:
    spec = SurvivalCampaignSpec(
        campaign_id="campaign:identity",
        experiment=experiment(),
        template=template(),
        fault_kinds=(SurvivalFaultKind.AUTHORITY_DROP,),
    )
    campaign = manufacture_survival_campaign(spec)
    llm_cases = [
        case for case in campaign.cases if case.run_case.cell.policy.policy_id == "llm"
    ]

    baseline = next(case for case in llm_cases if case.fault_plan is None)
    faulted = next(case for case in llm_cases if case.fault_plan is not None)
    baseline_doc = baseline.to_autofde_document()
    faulted_doc = faulted.to_autofde_document()

    assert baseline_doc["policy_id"] == faulted_doc["policy_id"] == "llm"
    assert baseline_doc["gymact"]["fault_plan_id"] is None
    assert faulted_doc["gymact"]["fault_plan_id"] == "fault:authority_drop:step-4"
    assert faulted_doc["gymact"]["synthetic"] is True
    assert faulted_doc["events"][-1]["authorized"] is False


def test_campaign_is_deterministic_for_same_exact_spec() -> None:
    spec = SurvivalCampaignSpec(
        campaign_id="campaign:replay",
        experiment=experiment(),
        template=template(),
        fault_kinds=(
            SurvivalFaultKind.WRONG_SUBJECT,
            SurvivalFaultKind.RECEIPT_DROP,
        ),
    )

    first = manufacture_survival_campaign(spec)
    second = manufacture_survival_campaign(spec)

    assert first == second
    assert first.campaign_digest == second.campaign_digest


def test_campaign_refuses_trace_template_beyond_scenario_horizon() -> None:
    with pytest.raises(
        ValidationError,
        match="SURVIVAL_TEMPLATE_EXCEEDS_SCENARIO_HORIZON",
    ):
        SurvivalCampaignSpec(
            campaign_id="campaign:bad-horizon",
            experiment=experiment(horizon=3),
            template=template(),
            fault_kinds=(SurvivalFaultKind.AUTHORITY_DROP,),
        )


def test_campaign_refuses_duplicate_fault_kinds_or_case_explosion() -> None:
    with pytest.raises(
        ValidationError,
        match="SURVIVAL_CAMPAIGN_FAULT_KIND_DUPLICATE",
    ):
        SurvivalCampaignSpec(
            campaign_id="campaign:duplicate",
            experiment=experiment(),
            template=template(),
            fault_kinds=(
                SurvivalFaultKind.TOOL_BLACKOUT,
                SurvivalFaultKind.TOOL_BLACKOUT,
            ),
        )

    with pytest.raises(
        ValidationError,
        match="SURVIVAL_CAMPAIGN_MAX_CASES_EXCEEDED",
    ):
        SurvivalCampaignSpec(
            campaign_id="campaign:too-wide",
            experiment=experiment(),
            template=template(),
            fault_kinds=(
                SurvivalFaultKind.AUTHORITY_DROP,
                SurvivalFaultKind.TOOL_BLACKOUT,
            ),
            max_campaign_cases=2,
        )
