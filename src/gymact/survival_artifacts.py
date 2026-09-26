"""Deterministic file artifacts for GymAct survival experiments.

Rendering is pure. Writing returns a receipt over the exact bytes written.
Artifacts carry construction evidence only and never imply that campaign cases
were executed.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Literal

from pydantic import Field

from gymact.models import FrozenModel
from gymact.survival_campaign import SurvivalCampaign
from gymact.survival_manifest import SurvivalExperimentManifest


class SurvivalArtifactReceipt(FrozenModel):
    artifact_kind: Literal["manifest-json", "campaign-jsonl"]
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    byte_length: int = Field(ge=0)
    record_count: int = Field(ge=0)
    authority: Literal["none"] = "none"
    actuation_performed: Literal[False] = False


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def render_survival_manifest(manifest: SurvivalExperimentManifest) -> bytes:
    return (_canonical_json(manifest.to_json()) + "\n").encode("utf-8")


def render_survival_campaign_jsonl(campaign: SurvivalCampaign) -> bytes:
    lines = [
        _canonical_json(case.to_autofde_document())
        for case in campaign.cases
    ]
    return (("\n".join(lines) + "\n") if lines else "").encode("utf-8")


def artifact_receipt(
    payload: bytes,
    *,
    artifact_kind: Literal["manifest-json", "campaign-jsonl"],
    record_count: int,
) -> SurvivalArtifactReceipt:
    return SurvivalArtifactReceipt(
        artifact_kind=artifact_kind,
        sha256=hashlib.sha256(payload).hexdigest(),
        byte_length=len(payload),
        record_count=record_count,
    )


def write_survival_manifest(
    path: Path,
    manifest: SurvivalExperimentManifest,
) -> SurvivalArtifactReceipt:
    payload = render_survival_manifest(manifest)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return artifact_receipt(
        payload,
        artifact_kind="manifest-json",
        record_count=len(manifest.cases),
    )


def write_survival_campaign_jsonl(
    path: Path,
    campaign: SurvivalCampaign,
) -> SurvivalArtifactReceipt:
    payload = render_survival_campaign_jsonl(campaign)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return artifact_receipt(
        payload,
        artifact_kind="campaign-jsonl",
        record_count=len(campaign.cases),
    )


__all__ = [
    "SurvivalArtifactReceipt",
    "artifact_receipt",
    "render_survival_campaign_jsonl",
    "render_survival_manifest",
    "write_survival_campaign_jsonl",
    "write_survival_manifest",
]
