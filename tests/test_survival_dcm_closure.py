from __future__ import annotations

from gymact import dcm
from gymact.survival_artifacts import SurvivalArtifactReceipt
from gymact.survival_campaign import SurvivalCampaign, SurvivalCampaignSpec
from gymact.survival_observation import SurvivalObservationClosure
from gymact.survival_suite import canonical_policy_suite


def test_dcm_exports_complete_survival_campaign_surface() -> None:
    assert dcm.SurvivalArtifactReceipt is SurvivalArtifactReceipt
    assert dcm.SurvivalCampaign is SurvivalCampaign
    assert dcm.SurvivalCampaignSpec is SurvivalCampaignSpec
    assert dcm.SurvivalObservationClosure is SurvivalObservationClosure
    assert dcm.canonical_policy_suite is canonical_policy_suite

    expected = {
        "SurvivalArtifactReceipt",
        "SurvivalCampaign",
        "SurvivalCampaignCase",
        "SurvivalCampaignSpec",
        "SurvivalObservationClosure",
        "SurvivalTraceTemplate",
        "artifact_receipt",
        "canonical_fault_kinds",
        "canonical_fault_suite",
        "canonical_policy_suite",
        "canonical_trace_template",
        "manufacture_survival_campaign",
        "qualify_observation_closure",
        "render_survival_campaign_jsonl",
        "render_survival_manifest",
        "write_survival_campaign_jsonl",
        "write_survival_manifest",
    }
    assert expected.issubset(set(dcm.__all__))
