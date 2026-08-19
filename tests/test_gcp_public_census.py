from __future__ import annotations

import httpx

from gymact.gyms.gcp_exact import GcpContractCensus
from gymact.gyms.gcp_public_census import (
    GcpPublicContractCensus,
    discovery_source_observation,
    load_cloud_docs_corpus,
)
from gymact.gyms.gcp_sources import (
    ContractArtifact,
    ContractSourceFamily,
    ContractSourceObservation,
    evaluate_source_admission,
)


def source(family: ContractSourceFamily) -> ContractSourceObservation:
    return ContractSourceObservation(
        family=family,
        disposition="ALIVE",
        artifacts=(
            ContractArtifact(
                family=family,
                identity=family.value,
                locator=f"https://example.test/{family.value}",
                digest="a" * 64,
                digest_algorithm="sha256",
                media_type="application/octet-stream",
            ),
        ),
        receipt=f"receipt:{family.value}",
    )


def test_discovery_census_becomes_receipted_source_observation() -> None:
    census = GcpContractCensus(
        apis=(),
        methods=(),
        schemas=(),
        directory_digest_sha256="b" * 64,
    )
    observation = discovery_source_observation(census)
    assert observation.family is ContractSourceFamily.DISCOVERY
    assert observation.disposition == "ALIVE"
    assert observation.receipt is not None
    assert len(observation.artifacts) == 1
    metadata = dict(observation.artifacts[0].metadata)
    assert metadata["api_versions"] == "0"
    assert metadata["methods"] == "0"


def test_cloud_docs_sitemap_index_closes_over_every_child() -> None:
    root = b'''<?xml version="1.0"?>
    <sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <sitemap><loc>https://cloud.google.com/sitemap-a.xml</loc></sitemap>
      <sitemap><loc>https://cloud.google.com/sitemap-b.xml</loc></sitemap>
    </sitemapindex>'''
    first = b'''<?xml version="1.0"?>
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <url><loc>https://cloud.google.com/a</loc><lastmod>2026-08-17</lastmod></url>
      <url><loc>https://cloud.google.com/shared</loc><lastmod>2026-08-17</lastmod></url>
    </urlset>'''
    second = b'''<?xml version="1.0"?>
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <url><loc>https://cloud.google.com/b</loc></url>
      <url><loc>https://cloud.google.com/shared</loc><lastmod>2026-08-18</lastmod></url>
    </urlset>'''

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url.endswith("/sitemap.xml"):
            return httpx.Response(200, content=root)
        if url.endswith("/sitemap-a.xml"):
            return httpx.Response(200, content=first)
        if url.endswith("/sitemap-b.xml"):
            return httpx.Response(200, content=second)
        return httpx.Response(404)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    observation = load_cloud_docs_corpus(client=client)
    assert observation.disposition == "ALIVE"
    assert observation.receipt is not None
    assert [artifact.identity for artifact in observation.artifacts] == [
        "https://cloud.google.com/a",
        "https://cloud.google.com/b",
        "https://cloud.google.com/shared",
    ]
    shared = observation.artifacts[-1]
    assert shared.metadata == (("lastmod", "2026-08-18"),)


def test_cloud_docs_unknown_sitemap_root_is_blocked() -> None:
    client = httpx.Client(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, content=b"<feed><entry/></feed>")
        )
    )
    observation = load_cloud_docs_corpus(client=client)
    assert observation.disposition == "BLOCKED"
    assert observation.receipt is None
    assert observation.reason == "UNSUPPORTED_SITEMAP_ROOT:feed"


def test_public_census_is_partial_until_credentialed_sources_arrive() -> None:
    discovery = source(ContractSourceFamily.DISCOVERY)
    googleapis = source(ContractSourceFamily.GOOGLEAPIS_PROTO)
    docs = source(ContractSourceFamily.HUMAN_DOCS)
    admission = evaluate_source_admission((discovery, googleapis, docs))
    census = GcpPublicContractCensus(
        discovery=discovery,
        googleapis=googleapis,
        human_docs=docs,
        admission=admission,
    )
    assert census.public_sources_alive
    assert not census.admission.complete
    summary = census.summary()
    assert summary["standing"] == "PARTIAL_ALIVE"
    assert not summary["whole_source_graph_complete"]
    assert "service-config" in summary["missing_required_sources"]
