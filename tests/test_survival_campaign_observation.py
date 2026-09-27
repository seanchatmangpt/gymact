from __future__ import annotations

from copy import deepcopy

from gymact.survival_campaign import (
    SurvivalCampaignSpec,
    SurvivalTraceTemplate,
    manufacture_survival_campaign,
)
from gymact.survival_campaign_observation import qualify_campaign_observation_closure
from gymact.survival_experiment import (
    Machinery,
    SurvivalExperiment,
    SurvivalPolicy,
    SurvivalScenario,
    SurvivalStep,
)
from gymact.survival_faults import SurvivalFaultKind


def campaign():
    experiment = SurvivalExperiment(
        experiment_id="closure-experiment",
        scenarios=(
            SurvivalScenario(
                scenario_id="world",
                subject="subject",
                workload_id="workload",
                horizon=3,
                terminal_predicate_ref="terminal",
            ),
        ),
        policies=(
            SurvivalPolicy(
                policy_id="formal",
                machinery=Machinery.FORMAL_GENERATED,
            ),
        ),
    )
    return manufacture_survival_campaign(
        SurvivalCampaignSpec(
            campaign_id="closure-campaign",
            experiment=experiment,
            template=SurvivalTraceTemplate(
                template_id="template",
                steps=(
                    SurvivalStep(step=1, phase="OBSERVE"),
                    SurvivalStep(
                        step=3,
                        phase="DO",
                        receipt_id="receipt:3",
                        replay_verified=True,
                    ),
                ),
            ),
            fault_kinds=(
                SurvivalFaultKind.AUTHORITY_DROP,
                SurvivalFaultKind.RECEIPT_DROP,
            ),
        )
    )


def documents(subject) -> list[dict]:
    return [case.to_autofde_document() for case in subject.cases]


def test_campaign_observation_closure_accepts_every_exact_variant_once() -> None:
    subject = campaign()

    closure = qualify_campaign_observation_closure(subject, documents(subject))

    assert closure.complete is True
    assert closure.standing == "STRUCTURAL"
    assert closure.expected_case_count == len(subject.cases) == 3
    assert closure.observed_unique_case_count == 3
    assert closure.missing_case_ids == ()
    assert closure.unknown_case_ids == ()
    assert closure.duplicate_case_ids == ()
    assert closure.identity_drift_episode_ids == ()


def test_campaign_closure_detects_missing_unknown_and_duplicate_variants() -> None:
    subject = campaign()
    rows = documents(subject)
    unknown = deepcopy(rows[0])
    unknown["episode_id"] = "unknown-campaign-case"

    closure = qualify_campaign_observation_closure(
        subject,
        [rows[0], rows[0], rows[1], unknown],
    )

    assert closure.complete is False
    assert closure.standing == "PARTIAL"
    assert rows[0]["episode_id"] in closure.duplicate_case_ids
    assert "unknown-campaign-case" in closure.unknown_case_ids
    assert rows[2]["episode_id"] in closure.missing_case_ids


def test_campaign_closure_detects_fault_or_run_case_identity_drift() -> None:
    subject = campaign()
    rows = documents(subject)

    faulted = next(row for row in rows if row["gymact"]["fault_plan_id"])
    faulted["gymact"]["fault_plan_id"] = "fault:wrong"
    baseline = next(row for row in rows if row["gymact"]["fault_plan_id"] is None)
    baseline["gymact"]["run_case_id"] = "wrong-run-case"

    closure = qualify_campaign_observation_closure(subject, rows)

    assert closure.complete is False
    assert set(closure.identity_drift_episode_ids) == {
        faulted["episode_id"],
        baseline["episode_id"],
    }


def test_campaign_closure_detects_policy_or_synthetic_claim_drift() -> None:
    subject = campaign()
    rows = documents(subject)
    rows[0]["policy_id"] = "other-policy"
    rows[1]["gymact"]["synthetic"] = False

    closure = qualify_campaign_observation_closure(subject, rows)

    assert closure.complete is False
    assert set(closure.identity_drift_episode_ids) == {
        rows[0]["episode_id"],
        rows[1]["episode_id"],
    }
