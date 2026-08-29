from __future__ import annotations

from gymact.gyms.gcp_public_families import derive_googleapis_family_observations
from gymact.gyms.gcp_sources import (
    ContractArtifact,
    ContractSourceFamily,
    ContractSourceObservation,
)


def _artifact(path: str) -> ContractArtifact:
    return ContractArtifact(
        family=ContractSourceFamily.GOOGLEAPIS_PROTO,
        identity=path,
        locator=f"https://github.com/googleapis/googleapis/blob/deadbeef/{path}",
        digest=(path.encode().hex() + "0" * 64)[:40],
        digest_algorithm="git-sha1",
        media_type="application/x-protobuf",
    )


def test_googleapis_tree_projects_every_static_semantic_family() -> None:
    source = ContractSourceObservation(
        family=ContractSourceFamily.GOOGLEAPIS_PROTO,
        disposition="ALIVE",
        artifacts=tuple(
            _artifact(path)
            for path in (
                "google/api/service.proto",
                "google/cloud/asset/v1/asset_service.proto",
                "google/cloud/audit/audit_log.proto",
                "google/iam/v1/iam_policy.proto",
                "google/api/serviceusage/v1/serviceusage.proto",
                "google/longrunning/operations.proto",
            )
        ),
        receipt="gcp-googleapis-tree:blake3:" + "a" * 64,
        source_revision="deadbeef" * 5,
    )

    projected = derive_googleapis_family_observations(source)
    assert [item.family for item in projected] == [
        ContractSourceFamily.SERVICE_CONFIG,
        ContractSourceFamily.ASSET_INVENTORY,
        ContractSourceFamily.AUDIT_LOGS,
        ContractSourceFamily.IAM,
        ContractSourceFamily.QUOTA,
        ContractSourceFamily.LONG_RUNNING_OPERATIONS,
    ]
    assert all(item.admitted for item in projected)
    assert all(item.source_revision == source.source_revision for item in projected)
    assert len({item.receipt for item in projected}) == 6


def test_missing_semantic_subcorpus_is_blocked_not_invented() -> None:
    source = ContractSourceObservation(
        family=ContractSourceFamily.GOOGLEAPIS_PROTO,
        disposition="ALIVE",
        artifacts=(_artifact("google/example/example.proto"),),
        receipt="gcp-googleapis-tree:blake3:" + "a" * 64,
        source_revision="deadbeef" * 5,
    )
    projected = derive_googleapis_family_observations(source)
    assert all(item.disposition == "BLOCKED" for item in projected)
    assert all(item.receipt is None for item in projected)
    assert all(item.reason == "NO_MATCHING_CANONICAL_CONTRACT_ARTIFACTS" for item in projected)
