"""Multi-source admission for externally observable GCP contracts.

The source graph is intentionally broader than Google Discovery. Exactness is
impossible unless every required source family has a unique, receipted
observation. Public corpora can be censused without credentials; credentialed
and empirical collectors feed the same admission type instead of being
silently approximated.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from hashlib import sha256
import json
from typing import Any, Iterable
from xml.etree import ElementTree

from blake3 import blake3
import httpx

__all__ = [
    "ContractArtifact",
    "ContractSourceFamily",
    "ContractSourceObservation",
    "GcpSourceAdmissionReport",
    "REQUIRED_SOURCE_FAMILIES",
    "evaluate_source_admission",
    "load_cloud_docs_sitemap",
    "load_googleapis_tree",
]


class ContractSourceFamily(StrEnum):
    DISCOVERY = "discovery"
    GOOGLEAPIS_PROTO = "googleapis-proto"
    SERVICE_CONFIG = "service-config"
    ASSET_INVENTORY = "asset-inventory"
    AUDIT_LOGS = "audit-logs"
    IAM = "iam"
    QUOTA = "quota"
    LONG_RUNNING_OPERATIONS = "long-running-operations"
    HUMAN_DOCS = "human-docs"
    EMPIRICAL_OBSERVATION = "empirical-observation"


REQUIRED_SOURCE_FAMILIES = frozenset(ContractSourceFamily)


@dataclass(frozen=True, slots=True)
class ContractArtifact:
    family: ContractSourceFamily
    identity: str
    locator: str
    digest: str
    digest_algorithm: str
    media_type: str
    metadata: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True, slots=True)
class ContractSourceObservation:
    family: ContractSourceFamily
    disposition: str
    artifacts: tuple[ContractArtifact, ...]
    receipt: str | None
    reason: str | None = None
    source_revision: str | None = None

    @property
    def admitted(self) -> bool:
        return self.disposition == "ALIVE" and bool(self.receipt) and bool(self.artifacts)


@dataclass(frozen=True, slots=True)
class GcpSourceAdmissionReport:
    required_sources: int
    alive_sources: int
    missing_sources: tuple[str, ...]
    duplicate_sources: tuple[str, ...]
    unreceipted_sources: tuple[str, ...]
    empty_sources: tuple[str, ...]
    non_alive_sources: tuple[tuple[str, str], ...]
    graph_digest_blake3: str

    @property
    def complete(self) -> bool:
        return (
            self.required_sources == self.alive_sources
            and not self.missing_sources
            and not self.duplicate_sources
            and not self.unreceipted_sources
            and not self.empty_sources
            and not self.non_alive_sources
        )


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _receipt(namespace: str, payload: Any) -> str:
    return f"{namespace}:blake3:{blake3(_canonical_json(payload).encode()).hexdigest()}"


def evaluate_source_admission(
    observations: Iterable[ContractSourceObservation],
) -> GcpSourceAdmissionReport:
    items = list(observations)
    counts: dict[ContractSourceFamily, int] = {}
    latest: dict[ContractSourceFamily, ContractSourceObservation] = {}
    for item in items:
        counts[item.family] = counts.get(item.family, 0) + 1
        latest[item.family] = item

    missing = tuple(sorted(family.value for family in REQUIRED_SOURCE_FAMILIES - set(latest)))
    duplicates = tuple(sorted(family.value for family, count in counts.items() if count > 1))
    unreceipted = tuple(
        sorted(
            family.value
            for family, item in latest.items()
            if family in REQUIRED_SOURCE_FAMILIES and item.disposition == "ALIVE" and not item.receipt
        )
    )
    empty = tuple(
        sorted(
            family.value
            for family, item in latest.items()
            if family in REQUIRED_SOURCE_FAMILIES and item.disposition == "ALIVE" and not item.artifacts
        )
    )
    non_alive = tuple(
        sorted(
            (family.value, item.disposition)
            for family, item in latest.items()
            if family in REQUIRED_SOURCE_FAMILIES and item.disposition != "ALIVE"
        )
    )
    alive = sum(
        1
        for family, item in latest.items()
        if family in REQUIRED_SOURCE_FAMILIES and item.admitted and counts.get(family) == 1
    )

    digest_payload = [
        {
            "family": family.value,
            "disposition": item.disposition,
            "receipt": item.receipt,
            "revision": item.source_revision,
            "artifacts": [
                {
                    "identity": artifact.identity,
                    "locator": artifact.locator,
                    "digest": artifact.digest,
                    "algorithm": artifact.digest_algorithm,
                    "media_type": artifact.media_type,
                }
                for artifact in sorted(item.artifacts, key=lambda value: value.identity)
            ],
        }
        for family, item in sorted(latest.items(), key=lambda pair: pair[0].value)
    ]
    graph_digest = blake3(_canonical_json(digest_payload).encode()).hexdigest()
    return GcpSourceAdmissionReport(
        required_sources=len(REQUIRED_SOURCE_FAMILIES),
        alive_sources=alive,
        missing_sources=missing,
        duplicate_sources=duplicates,
        unreceipted_sources=unreceipted,
        empty_sources=empty,
        non_alive_sources=non_alive,
        graph_digest_blake3=graph_digest,
    )


def load_googleapis_tree(
    *,
    client: httpx.Client | None = None,
    ref: str = "master",
    timeout: float = 60.0,
) -> ContractSourceObservation:
    """Census every canonical proto/config blob in googleapis/googleapis.

    Git tree blob SHAs bind exact file identities without downloading thousands
    of files. A truncated recursive tree is BLOCKED: partial topology can never
    be called complete.
    """
    own_client = client is None
    http = client or httpx.Client(timeout=timeout, follow_redirects=True)
    try:
        branch_url = f"https://api.github.com/repos/googleapis/googleapis/branches/{ref}"
        branch_response = http.get(branch_url)
        branch_response.raise_for_status()
        branch = branch_response.json()
        revision = str(branch["commit"]["sha"])
        tree_sha = str(branch["commit"]["commit"]["tree"]["sha"])
        tree_url = (
            f"https://api.github.com/repos/googleapis/googleapis/git/trees/{tree_sha}"
            "?recursive=1"
        )
        tree_response = http.get(tree_url)
        tree_response.raise_for_status()
        tree = tree_response.json()
        if tree.get("truncated"):
            return ContractSourceObservation(
                family=ContractSourceFamily.GOOGLEAPIS_PROTO,
                disposition="BLOCKED",
                artifacts=(),
                receipt=None,
                reason="GITHUB_RECURSIVE_TREE_TRUNCATED",
                source_revision=revision,
            )

        artifacts: list[ContractArtifact] = []
        for entry in tree.get("tree", []):
            if entry.get("type") != "blob":
                continue
            path = str(entry.get("path", ""))
            if not path.startswith("google/"):
                continue
            if path.endswith(".proto"):
                media_type = "application/x-protobuf"
            elif path.endswith((".yaml", ".yml")):
                media_type = "application/yaml"
            elif path.endswith(".json"):
                media_type = "application/json"
            else:
                continue
            blob_sha = str(entry.get("sha", ""))
            artifacts.append(
                ContractArtifact(
                    family=ContractSourceFamily.GOOGLEAPIS_PROTO,
                    identity=path,
                    locator=(
                        "https://github.com/googleapis/googleapis/blob/"
                        f"{revision}/{path}"
                    ),
                    digest=blob_sha,
                    digest_algorithm="git-sha1",
                    media_type=media_type,
                )
            )
        artifacts.sort(key=lambda value: value.identity)
        payload = {
            "revision": revision,
            "tree_sha": tree_sha,
            "artifacts": [(item.identity, item.digest) for item in artifacts],
        }
        return ContractSourceObservation(
            family=ContractSourceFamily.GOOGLEAPIS_PROTO,
            disposition="ALIVE" if artifacts else "BLOCKED",
            artifacts=tuple(artifacts),
            receipt=_receipt("gcp-googleapis-tree", payload) if artifacts else None,
            reason=None if artifacts else "NO_CANONICAL_INTERFACE_ARTIFACTS",
            source_revision=revision,
        )
    finally:
        if own_client:
            http.close()


def load_cloud_docs_sitemap(
    *,
    client: httpx.Client | None = None,
    url: str = "https://cloud.google.com/sitemap.xml",
    timeout: float = 60.0,
) -> ContractSourceObservation:
    """Census every URL published by the Google Cloud documentation sitemap."""
    own_client = client is None
    http = client or httpx.Client(timeout=timeout, follow_redirects=True)
    try:
        response = http.get(url)
        response.raise_for_status()
        raw = response.content
        root = ElementTree.fromstring(raw)
        namespace = "{http://www.sitemaps.org/schemas/sitemap/0.9}"
        artifacts: list[ContractArtifact] = []
        for node in root.findall(f"{namespace}url"):
            loc_node = node.find(f"{namespace}loc")
            if loc_node is None or not loc_node.text:
                continue
            locator = loc_node.text.strip()
            lastmod_node = node.find(f"{namespace}lastmod")
            lastmod = lastmod_node.text.strip() if lastmod_node is not None and lastmod_node.text else ""
            identity_payload = {"url": locator, "lastmod": lastmod}
            artifacts.append(
                ContractArtifact(
                    family=ContractSourceFamily.HUMAN_DOCS,
                    identity=locator,
                    locator=locator,
                    digest=sha256(_canonical_json(identity_payload).encode()).hexdigest(),
                    digest_algorithm="sha256",
                    media_type="text/html",
                    metadata=(("lastmod", lastmod),) if lastmod else (),
                )
            )
        artifacts.sort(key=lambda value: value.identity)
        sitemap_digest = sha256(raw).hexdigest()
        payload = {
            "sitemap_sha256": sitemap_digest,
            "artifacts": [(item.identity, item.digest) for item in artifacts],
        }
        return ContractSourceObservation(
            family=ContractSourceFamily.HUMAN_DOCS,
            disposition="ALIVE" if artifacts else "BLOCKED",
            artifacts=tuple(artifacts),
            receipt=_receipt("gcp-cloud-docs-sitemap", payload) if artifacts else None,
            reason=None if artifacts else "EMPTY_CLOUD_DOCS_SITEMAP",
            source_revision=sitemap_digest,
        )
    finally:
        if own_client:
            http.close()
