"""Bounded synthetic campaign manufacture for survival experiments.

A campaign cross-products already-manufactured SurvivalRunCase identities with
an explicit trace template and deterministic fault plans. This is useful for
simulation, mutation testing, and verifier qualification before real episodes
exist.

Campaign output is CONSTRUCT evidence only. Synthetic episodes are labeled as
such and no method performs external actuation or grants DO authority.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from gymact.evidence import digest
from gymact.models import FrozenModel
from gymact.survival_experiment import (
    SurvivalEpisode,
    SurvivalExperiment,
    SurvivalRunCase,
    SurvivalStep,
)
from gymact.survival_faults import (
    SurvivalFaultKind,
    SurvivalFaultPlan,
    apply_survival_fault_plan,
    manufacture_single_fault_plans,
)


class SurvivalTraceTemplate(FrozenModel):
    template_id: str = Field(min_length=1)
    steps: tuple[SurvivalStep, ...]

    @model_validator(mode="after")
    def validate_steps(self) -> "SurvivalTraceTemplate":
        numbers = [step.step for step in self.steps]
        if not numbers:
            raise ValueError("SURVIVAL_TEMPLATE_EMPTY")
        if len(numbers) != len(set(numbers)):
            raise ValueError("SURVIVAL_TEMPLATE_STEP_DUPLICATE")
        if numbers != sorted(numbers):
            raise ValueError("SURVIVAL_TEMPLATE_STEP_ORDER")
        return self

    @property
    def template_digest(self) -> str:
        return digest(self.model_dump(mode="json"))


class SurvivalCampaignSpec(FrozenModel):
    campaign_id: str = Field(min_length=1)
    experiment: SurvivalExperiment
    template: SurvivalTraceTemplate
    fault_kinds: tuple[SurvivalFaultKind, ...]
    include_baseline: bool = True
    llm_burst_magnitude: int = Field(ge=1, default=100)
    max_campaign_cases: int = Field(ge=1, le=2_000_000, default=250_000)
    authority: Literal["none"] = "none"
    actuation_performed: Literal[False] = False

    @model_validator(mode="after")
    def validate_horizon_and_width(self) -> "SurvivalCampaignSpec":
        max_step = max(step.step for step in self.template.steps)
        too_short = [
            scenario.scenario_id
            for scenario in self.experiment.scenarios
            if scenario.horizon < max_step
        ]
        if too_short:
            raise ValueError(
                "SURVIVAL_TEMPLATE_EXCEEDS_SCENARIO_HORIZON:" + ",".join(sorted(too_short))
            )
        if len(self.fault_kinds) != len(set(self.fault_kinds)):
            raise ValueError("SURVIVAL_CAMPAIGN_FAULT_KIND_DUPLICATE")
        if self.campaign_case_count > self.max_campaign_cases:
            raise ValueError(
                f"SURVIVAL_CAMPAIGN_MAX_CASES_EXCEEDED:"
                f"{self.campaign_case_count}>{self.max_campaign_cases}"
            )
        return self

    @property
    def fault_plans(self) -> tuple[SurvivalFaultPlan, ...]:
        return manufacture_single_fault_plans(
            self.template.steps,
            self.fault_kinds,
            llm_burst_magnitude=self.llm_burst_magnitude,
        )

    @property
    def variants_per_run_case(self) -> int:
        return len(self.fault_plans) + int(self.include_baseline)

    @property
    def campaign_case_count(self) -> int:
        return self.experiment.case_count * self.variants_per_run_case

    @property
    def spec_digest(self) -> str:
        return digest(self.model_dump(mode="json", exclude={"max_campaign_cases"}))


class SurvivalCampaignCase(FrozenModel):
    campaign_id: str
    campaign_spec_digest: str = Field(min_length=64, max_length=64)
    run_case: SurvivalRunCase
    template_digest: str = Field(min_length=64, max_length=64)
    fault_plan: SurvivalFaultPlan | None
    steps: tuple[SurvivalStep, ...]
    synthetic: Literal[True] = True
    authority: Literal["none"] = "none"
    actuation_performed: Literal[False] = False

    @property
    def variant_id(self) -> str:
        return "baseline" if self.fault_plan is None else self.fault_plan.plan_id

    @property
    def campaign_case_id(self) -> str:
        return (
            f"{self.run_case.case_id}::"
            f"{digest({'campaign': self.campaign_id, 'variant': self.variant_id})[:16]}"
        )

    def to_episode(self) -> SurvivalEpisode:
        return SurvivalEpisode(
            episode_id=self.campaign_case_id,
            cell=self.run_case.cell,
            run_case=self.run_case,
            steps=self.steps,
        )

    def to_autofde_document(self) -> dict:
        document = self.to_episode().to_autofde_document()
        document["gymact"]["synthetic"] = True
        document["gymact"]["campaign_id"] = self.campaign_id
        document["gymact"]["campaign_spec_digest"] = self.campaign_spec_digest
        document["gymact"]["template_digest"] = self.template_digest
        document["gymact"]["fault_plan_id"] = (
            self.fault_plan.plan_id if self.fault_plan is not None else None
        )
        document["gymact"]["fault_plan_digest"] = (
            self.fault_plan.plan_digest if self.fault_plan is not None else None
        )
        return document


class SurvivalCampaign(FrozenModel):
    campaign_id: str
    spec_digest: str = Field(min_length=64, max_length=64)
    cases: tuple[SurvivalCampaignCase, ...]
    authority: Literal["none"] = "none"
    actuation_performed: Literal[False] = False

    @property
    def campaign_digest(self) -> str:
        return digest(
            {
                "campaign_id": self.campaign_id,
                "spec_digest": self.spec_digest,
                "case_ids": [case.campaign_case_id for case in self.cases],
            }
        )


def manufacture_survival_campaign(spec: SurvivalCampaignSpec) -> SurvivalCampaign:
    """Manufacture the complete bounded run-case x fault-plan campaign."""

    cases: list[SurvivalCampaignCase] = []
    plans = spec.fault_plans
    for run_case in spec.experiment.cases():
        if spec.include_baseline:
            cases.append(
                SurvivalCampaignCase(
                    campaign_id=spec.campaign_id,
                    campaign_spec_digest=spec.spec_digest,
                    run_case=run_case,
                    template_digest=spec.template.template_digest,
                    fault_plan=None,
                    steps=spec.template.steps,
                )
            )
        for plan in plans:
            mutated, application = apply_survival_fault_plan(spec.template.steps, plan)
            if application.plan_digest != plan.plan_digest:
                raise AssertionError("SURVIVAL_CAMPAIGN_FAULT_RECEIPT_MISMATCH")
            cases.append(
                SurvivalCampaignCase(
                    campaign_id=spec.campaign_id,
                    campaign_spec_digest=spec.spec_digest,
                    run_case=run_case,
                    template_digest=spec.template.template_digest,
                    fault_plan=plan,
                    steps=mutated,
                )
            )

    if len(cases) != spec.campaign_case_count:
        raise AssertionError("SURVIVAL_CAMPAIGN_CARTESIAN_CLOSURE_BROKEN")
    if len({case.campaign_case_id for case in cases}) != len(cases):
        raise AssertionError("SURVIVAL_CAMPAIGN_CASE_ID_COLLISION")
    return SurvivalCampaign(
        campaign_id=spec.campaign_id,
        spec_digest=spec.spec_digest,
        cases=tuple(cases),
    )




class SurvivalCampaignReplay(FrozenModel):
    expected_campaign_digest: str = Field(min_length=64, max_length=64)
    replay_campaign_digest: str = Field(min_length=64, max_length=64)
    matched: bool
    mismatches: tuple[str, ...]
    authority: Literal["none"] = "none"
    actuation_performed: Literal[False] = False


def replay_survival_campaign(
    spec: SurvivalCampaignSpec,
    expected: SurvivalCampaign,
) -> SurvivalCampaignReplay:
    """Re-manufacture a campaign and compare exact variant identities/content."""

    replay = manufacture_survival_campaign(spec)
    mismatches: list[str] = []
    if expected.campaign_id != spec.campaign_id:
        mismatches.append("CAMPAIGN_ID_MISMATCH")
    if expected.spec_digest != spec.spec_digest:
        mismatches.append("CAMPAIGN_SPEC_DIGEST_MISMATCH")
    if len(expected.cases) != len(replay.cases):
        mismatches.append("CAMPAIGN_CASE_COUNT_MISMATCH")

    expected_by_id = {case.campaign_case_id: case for case in expected.cases}
    replay_by_id = {case.campaign_case_id: case for case in replay.cases}
    if len(expected_by_id) != len(expected.cases):
        mismatches.append("EXPECTED_CAMPAIGN_CASE_ID_DUPLICATE")
    if len(replay_by_id) != len(replay.cases):
        mismatches.append("REPLAY_CAMPAIGN_CASE_ID_DUPLICATE")

    missing = sorted(set(expected_by_id) - set(replay_by_id))
    extra = sorted(set(replay_by_id) - set(expected_by_id))
    mismatches.extend(f"CAMPAIGN_CASE_MISSING:{case_id}" for case_id in missing)
    mismatches.extend(f"CAMPAIGN_CASE_EXTRA:{case_id}" for case_id in extra)

    for case_id in sorted(set(expected_by_id) & set(replay_by_id)):
        if expected_by_id[case_id] != replay_by_id[case_id]:
            mismatches.append(f"CAMPAIGN_CASE_DRIFT:{case_id}")

    return SurvivalCampaignReplay(
        expected_campaign_digest=expected.campaign_digest,
        replay_campaign_digest=replay.campaign_digest,
        matched=not mismatches,
        mismatches=tuple(mismatches),
    )


__all__ = [
    "SurvivalCampaign",
    "SurvivalCampaignCase",
    "SurvivalCampaignSpec",
    "SurvivalCampaignReplay",
    "SurvivalTraceTemplate",
    "manufacture_survival_campaign",
    "replay_survival_campaign",
]
