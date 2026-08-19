"""Live, credential-free GCP public contract census.

This is deliberately not the whole-cloud crown. It executes the three source
families that Google publishes for unauthenticated bulk enumeration today:
Discovery REST metadata, canonical googleapis interface/config blobs, and the
Google Cloud documentation sitemap corpus. The remaining required families
enter through credentialed or empirical collectors and therefore remain open.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Any
from xml.etree import ElementTree

from blake3 import blake3
import httpx

from gymact.gyms.gcp_exact import GcpContractCensus, load_discovery_census
from gymact.gyms.gcp_sources import (
    ContractArtifact,
    ContractSourceFamily,
    ContractSourceObservation,
    GcpSourceAdmissionReport,
    evaluate_source_admission,
    load_googleapis_tree,
)

__all__ = [
    "GcpPublicContractCensus",
    "discovery_source_observation",
    "load_cloud_docs_corpus",
    "load_public_contract_census",
]

_SITEMAP_NS = "{http://www.sitemaps.org/schemas/sitemap/0.9}"


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _receipt(namespace: str, payload: Any) -> str:
    return f"{namespace}:blake3:{blake3(_canonical_json(payload).encode()).hexdigest()}"


def discovery_source_observation(census: GcpContractCensus) -> ContractSourceObservation:
    artifact = ContractArtifact(
        family=ContractSourceFamily.DISCOVERY,
        identity=f"google-discovery:{census.contract_digest_blake3}",
        locator="https://discovery.googleapis.com/discovery/v1/apis",
        digest=census.contract_digest_blake3,
        digest_algorithm="blake3-256",
        media_type="application/json",
        metadata=(
            ("api_versions", str(len(census.apis))),
            ("methods", str(len(census.methods))),
            ("schemas", str(len(census.schemas))),
            ("directory_sha256", census.directory_digest_sha256),
        ),
    )
    return ContractSourceObservation(
        family=ContractSourceFamily.DISCOVERY,
        disposition="ALIVE",
        artifacts=(artifact,),
        receipt=f"gcp-discovery:blake3:{census.contract_digest_blake3}",
        source_revision=census.directory_digest_sha256,
    )


def load_cloud_docs_corpus(
    *,
    client: httpx.Client | None = None,
    root_url: str = "https://cloud.google.com/sitemap.xml",
    timeout: float = 60.0,
) -> ContractSourceObservation:
    """Census a sitemap or sitemap-index closure without silently truncating it."""
    own_client = client is None
    http = client or httpx.Client(timeout=timeout, follow_redirects=True)
    try:
        pending: deque[str] = deque([root_url])
        visited: set[str] = set()
        documents: dict[str, str] = {}
        sitemap_digests: list[tuple[str, str]] = []

        while pending:
            sitemap_url = pending.popleft()
            if sitemap_url in visited:
                continue
            visited.add(sitemap_url)
            response = http.get(sitemap_url)
            response.raise_for_status()
            raw = response.content
            sitemap_digests.append((sitemap_url, sha256(raw).hexdigest()))
            root = ElementTree.fromstring(raw)
            local_name = root.tag.rsplit("}", 1)[-1]

            if local_name == "sitemapindex":
                for sitemap in root.findall(f"{_SITEMAP_NS}sitemap"):
                    loc = sitemap.find(f"{_SITEMAP_NS}loc")
                    if loc is not None and loc.text:
                        child = loc.text.strip()
                        if child not in visited:
                            pending.append(child)
                continue
            if local_name != "urlset":
                return ContractSourceObservation(
                    family=ContractSourceFamily.HUMAN_DOCS,
                    disposition="BLOCKED",
                    artifacts=(),
                    receipt=None,
                    reason=f"UNSUPPORTED_SITEMAP_ROOT:{local_name}",
                )

            for node in root.findall(f"{_SITEMAP_NS}url"):
                loc = node.find(f"{_SITEMAP_NS}loc")
                if loc is None or not loc.text:
                    continue
                url = loc.text.strip()
                lastmod_node = node.find(f"{_SITEMAP_NS}lastmod")
                lastmod = (
                    lastmod_node.text.strip()
                    if lastmod_node is not None and lastmod_node.text
                    else ""
                )
                previous = documents.get(url)
                if previous is None or lastmod > previous:
                    documents[url] = lastmod

        artifacts = tuple(
            ContractArtifact(
                family=ContractSourceFamily.HUMAN_DOCS,
                identity=url,
                locator=url,
                digest=sha256(_canonical_json({"url": url, "lastmod": lastmod}).encode()).hexdigest(),
                digest_algorithm="sha256",
                media_type="text/html",
                metadata=(("lastmod", lastmod),) if lastmod else (),
            )
            for url, lastmod in sorted(documents.items())
        )
        payload = {
            "root": root_url,
            "sitemaps": sorted(sitemap_digests),
            "documents": [(item.identity, item.digest) for item in artifacts],
        }
        corpus_digest = blake3(_canonical_json(payload).encode()).hexdigest()
        return ContractSourceObservation(
            family=ContractSourceFamily.HUMAN_DOCS,
            disposition="ALIVE" if artifacts else "BLOCKED",
            artifacts=artifacts,
            receipt=f"gcp-cloud-docs:blake3:{corpus_digest}" if artifacts else None,
            reason=None if artifacts else "EMPTY_CLOUD_DOCS_CORPUS",
            source_revision=corpus_digest,
        )
    finally:
        if own_client:
            http.close()


@dataclass(frozen=True, slots=True)
class GcpPublicContractCensus:
    discovery: ContractSourceObservation
    googleapis: ContractSourceObservation
    human_docs: ContractSourceObservation
    admission: GcpSourceAdmissionReport

    @property
    def public_sources_alive(self) -> bool:
        return all(
            source.admitted
            for source in (self.discovery, self.googleapis, self.human_docs)
        )

    def summary(self) -> dict[str, Any]:
        return {
            "standing": "PARTIAL_ALIVE" if self.public_sources_alive else "BLOCKED",
            "public_sources_alive": self.public_sources_alive,
            "whole_source_graph_complete": self.admission.complete,
            "source_graph_digest_blake3": self.admission.graph_digest_blake3,
            "sources": {
                source.family.value: {
                    "disposition": source.disposition,
                    "artifact_count": len(source.artifacts),
                    "receipt": source.receipt,
                    "source_revision": source.source_revision,
                    "reason": source.reason,
                }
                for source in (self.discovery, self.googleapis, self.human_docs)
            },
            "missing_required_sources": list(self.admission.missing_sources),
        }


def load_public_contract_census(*, timeout: float = 60.0) -> GcpPublicContractCensus:
    discovery_census = load_discovery_census(timeout=timeout)
    discovery = discovery_source_observation(discovery_census)
    googleapis = load_googleapis_tree(timeout=timeout)
    human_docs = load_cloud_docs_corpus(timeout=timeout)
    admission = evaluate_source_admission((discovery, googleapis, human_docs))
    return GcpPublicContractCensus(
        discovery=discovery,
        googleapis=googleapis,
        human_docs=human_docs,
        admission=admission,
    )
