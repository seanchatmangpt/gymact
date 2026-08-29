"""Derive typed GCP contract families from the exact canonical googleapis tree.

The googleapis repository contains multiple semantic sub-corpora. Treating the
whole tree as one source hides whether IAM, quota, LRO, audit, asset, and service
configuration contracts were actually observed. This module projects those
sub-corpora into independent, receipted admission families without duplicating
or downloading source blobs.
"""

from __future__ import annotations

from collections.abc import Callable
import json

from blake3 import blake3

from gymact.gyms.gcp_sources import (
    ContractArtifact,
    ContractSourceFamily,
    ContractSourceObservation,
)

__all__ = ["derive_googleapis_family_observations"]


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _project(
    source: ContractSourceObservation,
    family: ContractSourceFamily,
    predicate: Callable[[str], bool],
) -> ContractSourceObservation:
    selected = tuple(
        ContractArtifact(
            family=family,
            identity=item.identity,
            locator=item.locator,
            digest=item.digest,
            digest_algorithm=item.digest_algorithm,
            media_type=item.media_type,
            metadata=item.metadata,
        )
        for item in source.artifacts
        if predicate(item.identity.lower())
    )
    if not source.admitted:
        return ContractSourceObservation(
            family=family,
            disposition="BLOCKED",
            artifacts=(),
            receipt=None,
            reason=f"UPSTREAM_GOOGLEAPIS_NOT_ADMITTED:{source.disposition}",
            source_revision=source.source_revision,
        )
    if not selected:
        return ContractSourceObservation(
            family=family,
            disposition="BLOCKED",
            artifacts=(),
            receipt=None,
            reason="NO_MATCHING_CANONICAL_CONTRACT_ARTIFACTS",
            source_revision=source.source_revision,
        )
    payload = {
        "family": family.value,
        "revision": source.source_revision,
        "artifacts": [(item.identity, item.digest) for item in selected],
    }
    digest = blake3(_canonical_json(payload).encode()).hexdigest()
    return ContractSourceObservation(
        family=family,
        disposition="ALIVE",
        artifacts=selected,
        receipt=f"gcp-googleapis-{family.value}:blake3:{digest}",
        source_revision=source.source_revision,
    )


def derive_googleapis_family_observations(
    source: ContractSourceObservation,
) -> tuple[ContractSourceObservation, ...]:
    """Project six required semantic families from one exact tree receipt."""

    def service_config(path: str) -> bool:
        return (
            path in {
                "google/api/service.proto",
                "google/api/config_change.proto",
                "google/api/backend.proto",
                "google/api/http.proto",
            }
            or path.endswith((".yaml", ".yml", ".json"))
        )

    def asset_inventory(path: str) -> bool:
        return path.startswith("google/cloud/asset/") or "/asset/" in path

    def audit_logs(path: str) -> bool:
        return path.startswith("google/cloud/audit/") or "audit_log" in path or "/audit/" in path

    def iam(path: str) -> bool:
        return path.startswith("google/iam/") or "/iam/" in path or path.endswith("/iam_policy.proto")

    def quota(path: str) -> bool:
        return "quota" in path or path.startswith("google/api/serviceusage/") or "/serviceusage/" in path

    def lro(path: str) -> bool:
        return path.startswith("google/longrunning/") or "longrunning" in path

    rules = (
        (ContractSourceFamily.SERVICE_CONFIG, service_config),
        (ContractSourceFamily.ASSET_INVENTORY, asset_inventory),
        (ContractSourceFamily.AUDIT_LOGS, audit_logs),
        (ContractSourceFamily.IAM, iam),
        (ContractSourceFamily.QUOTA, quota),
        (ContractSourceFamily.LONG_RUNNING_OPERATIONS, lro),
    )
    return tuple(_project(source, family, predicate) for family, predicate in rules)
