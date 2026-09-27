from __future__ import annotations

import hashlib
import json
from pathlib import Path

from gymact.survival_artifacts import (
    render_survival_campaign_jsonl,
    render_survival_manifest,
    write_survival_campaign_jsonl,
    write_survival_manifest,
)
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
from gymact.survival_manifest import build_survival_manifest


def experiment() -> SurvivalExperiment:
    return SurvivalExperiment(
        experiment_id="artifact-experiment",
        scenarios=(
            SurvivalScenario(
                scenario_id="world",
                subject="git:seanchatmangpt/gymact@0123456789abcdef",
                workload_id="sha256:artifact-workload",
                horizon=3,
                terminal_predicate_ref="urn:predicate:done",
            ),
        ),
        policies=(
            SurvivalPolicy(
                policy_id="formal",
                machinery=Machinery.FORMAL_GENERATED,
            ),
        ),
    )


def campaign():
    return manufacture_survival_campaign(
        SurvivalCampaignSpec(
            campaign_id="artifact-campaign",
            experiment=experiment(),
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
            fault_kinds=(SurvivalFaultKind.AUTHORITY_DROP,),
        )
    )


def test_manifest_render_is_canonical_and_replay_stable() -> None:
    manifest = build_survival_manifest(experiment())

    first = render_survival_manifest(manifest)
    second = render_survival_manifest(manifest)

    assert first == second
    assert first.endswith(b"\n")
    document = json.loads(first)
    assert document["manifest_digest"] == manifest.manifest_digest


def test_campaign_jsonl_is_deterministic_and_one_document_per_case() -> None:
    subject = campaign()

    first = render_survival_campaign_jsonl(subject)
    second = render_survival_campaign_jsonl(subject)

    assert first == second
    rows = [json.loads(line) for line in first.decode().splitlines()]
    assert len(rows) == len(subject.cases) == 2
    assert all(row["gymact"]["synthetic"] is True for row in rows)
    assert {row["gymact"]["fault_plan_id"] for row in rows} == {
        None,
        "fault:authority_drop:step-3",
    }


def test_write_receipts_bind_exact_bytes_and_record_counts(tmp_path: Path) -> None:
    manifest = build_survival_manifest(experiment())
    subject = campaign()
    manifest_path = tmp_path / "manifest.json"
    campaign_path = tmp_path / "campaign.jsonl"

    manifest_receipt = write_survival_manifest(manifest_path, manifest)
    campaign_receipt = write_survival_campaign_jsonl(campaign_path, subject)

    assert manifest_receipt.sha256 == hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    assert campaign_receipt.sha256 == hashlib.sha256(campaign_path.read_bytes()).hexdigest()
    assert manifest_receipt.record_count == len(manifest.cases)
    assert campaign_receipt.record_count == len(subject.cases)
    assert manifest_receipt.authority == "none"
    assert campaign_receipt.actuation_performed is False
