from __future__ import annotations

import httpx

from gymact.gyms.gcp_discovery_live import load_resilient_discovery_census
from gymact.gyms.gcp_exact import (
    DiscoveryApi,
    DiscoveryMethod,
    DiscoverySchema,
    GcpContractCensus,
)
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


def _nonempty_census() -> GcpContractCensus:
    return GcpContractCensus(
        apis=(
            DiscoveryApi(
                name="example",
                version="v1",
                title="Example",
                preferred=True,
                discovery_url="https://example.test/discovery",
            ),
        ),
        methods=(
            DiscoveryMethod(
                api="example",
                version="v1",
                resource_path="resources",
                name="get",
                http_method="GET",
                path="v1/{name}",
                request_schema=None,
                response_schema="Resource",
                scopes=(),
            ),
        ),
        schemas=(
            DiscoverySchema(
                api="example",
                version="v1",
                name="Resource",
                canonical_json='{"type":"object"}',
                digest_sha256="c" * 64,
            ),
        ),
        directory_digest_sha256="b" * 64,
    )


def test_empty_discovery_census_is_blocked() -> None:
    census = GcpContractCensus(
        apis=(),
        methods=(),
        schemas=(),
        directory_digest_sha256="b" * 64,
    )
    observation = discovery_source_observation(census)
    assert observation.family is ContractSourceFamily.DISCOVERY
    assert observation.disposition == "BLOCKED"
    assert observation.receipt is None
    assert observation.artifacts == ()
    assert observation.reason == "EMPTY_OR_INCOMPLETE_DISCOVERY_CENSUS"


def test_nonempty_discovery_census_becomes_receipted_source_observation() -> None:
    observation = discovery_source_observation(_nonempty_census())
    assert observation.disposition == "ALIVE"
    assert observation.receipt is not None
    assert len(observation.artifacts) == 1
    metadata = dict(observation.artifacts[0].metadata)
    assert metadata["advertised_api_versions"] == "1"
    assert metadata["available_api_versions"] == "1"
    assert metadata["unavailable_api_versions"] == "0"
    assert metadata["transiently_unavailable_api_versions"] == "0"
    assert metadata["methods"] == "1"
    assert metadata["schemas"] == "1"


def test_stale_advertised_discovery_document_is_preserved_not_dropped() -> None:
    directory = {
        "items": [
            {
                "name": "example",
                "version": "v1",
                "title": "Example",
                "preferred": True,
                "discoveryRestUrl": "https://example.test/discovery",
            },
            {
                "name": "stale",
                "version": "v1alpha1",
                "title": "Stale",
                "preferred": False,
                "discoveryRestUrl": "https://stale.test/discovery",
            },
        ]
    }
    document = {
        "name": "example",
        "version": "v1",
        "methods": {
            "get": {
                "httpMethod": "GET",
                "path": "v1/resources/{name}",
                "response": {"$ref": "Resource"},
            }
        },
        "schemas": {"Resource": {"type": "object"}},
    }

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url == "https://discovery.googleapis.com/discovery/v1/apis":
            return httpx.Response(200, json=directory)
        if url == "https://example.test/discovery":
            return httpx.Response(200, json=document)
        if url == "https://stale.test/discovery":
            return httpx.Response(404, content=b"gone")
        return httpx.Response(500)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    result = load_resilient_discovery_census(client=client)
    assert result.complete_probe
    assert result.advertised_entries == 2
    assert [item.identity for item in result.unavailable] == ["stale:v1alpha1"]

    observation = discovery_source_observation(result)
    assert observation.admitted
    metadata = dict(observation.artifacts[0].metadata)
    assert metadata["advertised_api_versions"] == "2"
    assert metadata["available_api_versions"] == "1"
    assert metadata["unavailable_api_versions"] == "1"
    assert metadata["transiently_unavailable_api_versions"] == "0"
    unavailable = observation.artifacts[1]
    assert unavailable.identity == "google-discovery-unavailable:stale:v1alpha1"
    assert dict(unavailable.metadata)["status_code"] == "404"
    assert dict(unavailable.metadata)["transient"] == "false"


def test_exhausted_transient_discovery_is_receipted_partial_not_alive() -> None:
    directory = {
        "items": [
            {
                "name": "example",
                "version": "v1",
                "title": "Example",
                "preferred": True,
                "discoveryRestUrl": "https://example.test/discovery",
            },
            {
                "name": "flaky",
                "version": "v1beta1",
                "title": "Flaky",
                "preferred": True,
                "discoveryRestUrl": "https://flaky.test/discovery",
            },
        ]
    }
    document = {
        "name": "example",
        "version": "v1",
        "methods": {"get": {"httpMethod": "GET", "path": "v1/{name}", "response": {"$ref": "R"}}},
        "schemas": {"R": {"type": "object"}},
    }

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url == "https://discovery.googleapis.com/discovery/v1/apis":
            return httpx.Response(200, json=directory)
        if url == "https://example.test/discovery":
            return httpx.Response(200, json=document)
        if url == "https://flaky.test/discovery":
            return httpx.Response(502, content=b"upstream unavailable")
        return httpx.Response(500)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    result = load_resilient_discovery_census(client=client)
    assert result.complete_probe
    assert result.has_transient_gaps

    observation = discovery_source_observation(result)
    assert observation.disposition == "PARTIAL_ALIVE"
    assert not observation.admitted
    assert observation.receipt is not None
    assert observation.artifacts
    assert observation.reason == "TRANSIENT_DISCOVERY_DOCUMENTS_UNAVAILABLE"
    metadata = dict(observation.artifacts[0].metadata)
    assert metadata["transiently_unavailable_api_versions"] == "1"
    transient = observation.artifacts[1]
    assert dict(transient.metadata)["status_code"] == "502"
    assert dict(transient.metadata)["transient"] == "true"


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


def test_public_census_closes_nine_families_and_leaves_only_empirical_open() -> None:
    discovery = source(ContractSourceFamily.DISCOVERY)
    googleapis = source(ContractSourceFamily.GOOGLEAPIS_PROTO)
    derived = tuple(
        source(family)
        for family in (
            ContractSourceFamily.SERVICE_CONFIG,
            ContractSourceFamily.ASSET_INVENTORY,
            ContractSourceFamily.AUDIT_LOGS,
            ContractSourceFamily.IAM,
            ContractSourceFamily.QUOTA,
            ContractSourceFamily.LONG_RUNNING_OPERATIONS,
        )
    )
    docs = source(ContractSourceFamily.HUMAN_DOCS)
    admission = evaluate_source_admission((discovery, googleapis, *derived, docs))
    census = GcpPublicContractCensus(
        discovery=discovery,
        googleapis=googleapis,
        derived_sources=derived,
        human_docs=docs,
        admission=admission,
    )
    assert census.public_sources_alive
    assert census.public_sources_receipted
    assert not census.admission.complete
    summary = census.summary()
    assert summary["standing"] == "PARTIAL_ALIVE"
    assert summary["public_source_count"] == 9
    assert not summary["whole_source_graph_complete"]
    assert summary["missing_required_sources"] == ["empirical-observation"]


def test_receipted_partial_public_source_stays_partial_and_not_admitted() -> None:
    discovery = ContractSourceObservation(
        family=ContractSourceFamily.DISCOVERY,
        disposition="PARTIAL_ALIVE",
        artifacts=source(ContractSourceFamily.DISCOVERY).artifacts,
        receipt="receipt:partial-discovery",
        reason="TRANSIENT_DISCOVERY_DOCUMENTS_UNAVAILABLE",
    )
    googleapis = source(ContractSourceFamily.GOOGLEAPIS_PROTO)
    derived = tuple(
        source(family)
        for family in (
            ContractSourceFamily.SERVICE_CONFIG,
            ContractSourceFamily.ASSET_INVENTORY,
            ContractSourceFamily.AUDIT_LOGS,
            ContractSourceFamily.IAM,
            ContractSourceFamily.QUOTA,
            ContractSourceFamily.LONG_RUNNING_OPERATIONS,
        )
    )
    docs = source(ContractSourceFamily.HUMAN_DOCS)
    admission = evaluate_source_admission((discovery, googleapis, *derived, docs))
    census = GcpPublicContractCensus(
        discovery=discovery,
        googleapis=googleapis,
        derived_sources=derived,
        human_docs=docs,
        admission=admission,
    )
    assert not census.public_sources_alive
    assert census.public_sources_receipted
    assert census.standing == "PARTIAL_ALIVE"
    assert ("discovery", "PARTIAL_ALIVE") in admission.non_alive_sources
