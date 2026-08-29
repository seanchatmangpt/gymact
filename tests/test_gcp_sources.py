from __future__ import annotations

import httpx

from gymact.gyms.gcp_sources import (
    ContractArtifact,
    ContractSourceFamily,
    ContractSourceObservation,
    REQUIRED_SOURCE_FAMILIES,
    evaluate_source_admission,
    load_cloud_docs_sitemap,
    load_googleapis_tree,
)


def artifact(family: ContractSourceFamily, identity: str) -> ContractArtifact:
    return ContractArtifact(
        family=family,
        identity=identity,
        locator=f"https://example.test/{identity}",
        digest="a" * 64,
        digest_algorithm="sha256",
        media_type="application/octet-stream",
    )


def alive(family: ContractSourceFamily) -> ContractSourceObservation:
    return ContractSourceObservation(
        family=family,
        disposition="ALIVE",
        artifacts=(artifact(family, family.value),),
        receipt=f"receipt:{family.value}",
    )


def test_source_admission_requires_every_family_receipted_and_nonempty() -> None:
    complete = evaluate_source_admission(alive(family) for family in REQUIRED_SOURCE_FAMILIES)
    assert complete.complete
    assert complete.alive_sources == 10
    assert len(complete.graph_digest_blake3) == 64

    missing = evaluate_source_admission(
        alive(family)
        for family in REQUIRED_SOURCE_FAMILIES
        if family is not ContractSourceFamily.AUDIT_LOGS
    )
    assert not missing.complete
    assert missing.missing_sources == ("audit-logs",)

    observations = [alive(family) for family in REQUIRED_SOURCE_FAMILIES]
    observations.append(alive(ContractSourceFamily.IAM))
    duplicated = evaluate_source_admission(observations)
    assert not duplicated.complete
    assert duplicated.duplicate_sources == ("iam",)


def test_unreceipted_alive_source_cannot_be_admitted() -> None:
    observations = [alive(family) for family in REQUIRED_SOURCE_FAMILIES]
    index = next(
        i for i, item in enumerate(observations) if item.family is ContractSourceFamily.QUOTA
    )
    observations[index] = ContractSourceObservation(
        family=ContractSourceFamily.QUOTA,
        disposition="ALIVE",
        artifacts=(artifact(ContractSourceFamily.QUOTA, "quota"),),
        receipt=None,
    )
    report = evaluate_source_admission(observations)
    assert not report.complete
    assert report.unreceipted_sources == ("quota",)
    assert report.alive_sources == 9


def test_googleapis_tree_censuses_proto_and_config_blobs() -> None:
    branch = {
        "commit": {
            "sha": "1" * 40,
            "commit": {"tree": {"sha": "2" * 40}},
        }
    }
    tree = {
        "truncated": False,
        "tree": [
            {"path": "google/cloud/example/v1/example.proto", "type": "blob", "sha": "3" * 40},
            {"path": "google/cloud/example/v1/example_v1.yaml", "type": "blob", "sha": "4" * 40},
            {"path": "google/cloud/example/v1/README.md", "type": "blob", "sha": "5" * 40},
            {"path": "README.md", "type": "blob", "sha": "6" * 40},
        ],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        if "/branches/master" in str(request.url):
            return httpx.Response(200, json=branch)
        if "/git/trees/" in str(request.url):
            return httpx.Response(200, json=tree)
        return httpx.Response(404)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    result = load_googleapis_tree(client=client)
    assert result.disposition == "ALIVE"
    assert result.receipt is not None
    assert result.source_revision == "1" * 40
    assert [item.identity for item in result.artifacts] == [
        "google/cloud/example/v1/example.proto",
        "google/cloud/example/v1/example_v1.yaml",
    ]


def test_truncated_googleapis_tree_is_blocked_not_partial_success() -> None:
    branch = {
        "commit": {
            "sha": "1" * 40,
            "commit": {"tree": {"sha": "2" * 40}},
        }
    }

    def handler(request: httpx.Request) -> httpx.Response:
        if "/branches/master" in str(request.url):
            return httpx.Response(200, json=branch)
        return httpx.Response(200, json={"truncated": True, "tree": []})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    result = load_googleapis_tree(client=client)
    assert result.disposition == "BLOCKED"
    assert result.receipt is None
    assert result.reason == "GITHUB_RECURSIVE_TREE_TRUNCATED"


def test_cloud_docs_sitemap_is_censused_with_lastmod() -> None:
    xml = b'''<?xml version="1.0" encoding="UTF-8"?>
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <url><loc>https://cloud.google.com/a</loc><lastmod>2026-08-18</lastmod></url>
      <url><loc>https://cloud.google.com/b</loc></url>
    </urlset>'''

    client = httpx.Client(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, content=xml))
    )
    result = load_cloud_docs_sitemap(client=client)
    assert result.disposition == "ALIVE"
    assert result.receipt is not None
    assert len(result.artifacts) == 2
    assert result.artifacts[0].metadata == (("lastmod", "2026-08-18"),)
