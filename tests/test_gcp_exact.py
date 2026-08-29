from __future__ import annotations

import json

import httpx

from gymact.gyms.gcp_exact import (
    CoverageDisposition,
    GcpCoverageRecord,
    GcpCoverageReport,
    ObservationProjection,
    build_contract_rdf,
    compare_observations,
    flatten_discovery_document,
    load_discovery_census,
    normalize_http_response,
)


def _discovery_doc(name: str, version: str) -> dict[str, object]:
    return {
        "name": name,
        "version": version,
        "methods": {
            "rootCall": {
                "httpMethod": "POST",
                "path": "root:call",
                "request": {"$ref": "Request"},
                "response": {"$ref": "Response"},
            }
        },
        "resources": {
            "projects": {
                "resources": {
                    "locations": {
                        "methods": {
                            "get": {
                                "httpMethod": "GET",
                                "path": "v1/{name=projects/*/locations/*}",
                                "response": {"$ref": "Location"},
                                "scopes": ["scope-b", "scope-a"],
                            }
                        }
                    }
                }
            }
        },
        "schemas": {
            "Response": {"type": "object", "properties": {"ok": {"type": "boolean"}}},
            "Request": {"type": "object"},
            "Location": {"type": "object", "id": "Location"},
        },
    }


def _census():
    document = _discovery_doc("example", "v1")
    directory = {
        "items": [
            {
                "name": "example",
                "version": "v1",
                "title": "Example",
                "preferred": True,
                "discoveryRestUrl": "https://example.test/discovery",
                "documentationLink": "https://docs.example/example",
            }
        ]
    }

    def handler(request: httpx.Request) -> httpx.Response:
        if "discovery.googleapis.com" in str(request.url):
            return httpx.Response(200, json=directory)
        return httpx.Response(200, json=document)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    return load_discovery_census(client=client)


def _alive_record(method_id: str, index: int) -> GcpCoverageRecord:
    response = httpx.Response(
        200,
        headers={"content-type": "application/json", "etag": '"abc"'},
        json={"ok": True, "requestId": f"real-{index}"},
    )
    projection = ObservationProjection(ignored_json_fields=frozenset({"requestId"}))
    real = normalize_http_response(response, projection=projection)
    simulator = normalize_http_response(response, projection=projection)
    evidence = compare_observations(
        method_id=method_id,
        real=real,
        simulator=simulator,
        real_receipt=f"real-{index}",
        simulator_receipt=f"sim-{index}",
        projection=projection,
    )
    return evidence.coverage_record()


def test_flatten_discovery_document_recurses_and_hashes_schemas() -> None:
    methods, schemas = flatten_discovery_document(_discovery_doc("example", "v1"))

    assert [method.identity for method in methods] == [
        "example:v1:projects.locations.get",
        "example:v1:rootCall",
    ]
    nested = methods[0]
    assert nested.http_method == "GET"
    assert nested.scopes == ("scope-a", "scope-b")
    assert len(schemas) == 3
    assert all(len(schema.digest_sha256) == 64 for schema in schemas)


def test_live_census_contract_uses_every_directory_entry() -> None:
    directory = {
        "items": [
            {
                "name": "alpha",
                "version": "v1",
                "title": "Alpha",
                "preferred": True,
                "discoveryRestUrl": "https://alpha.example/discovery",
                "documentationLink": "https://docs.example/alpha",
            },
            {
                "name": "beta",
                "version": "v1beta1",
                "title": "Beta",
                "preferred": False,
                "discoveryRestUrl": "https://beta.example/discovery",
            },
        ]
    }

    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url) == "https://discovery.googleapis.com/discovery/v1/apis":
            return httpx.Response(200, json=directory)
        if str(request.url) == "https://alpha.example/discovery":
            return httpx.Response(200, json=_discovery_doc("alpha", "v1"))
        if str(request.url) == "https://beta.example/discovery":
            return httpx.Response(200, json=_discovery_doc("beta", "v1beta1"))
        return httpx.Response(404)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    census = load_discovery_census(client=client)

    assert [api.identity for api in census.apis] == ["alpha:v1", "beta:v1beta1"]
    assert len(census.methods) == 4
    assert len(census.schemas) == 6
    assert len(census.directory_digest_sha256) == 64
    assert len(census.contract_digest_blake3) == 64


def test_differential_evidence_ignores_only_declared_projection_fields() -> None:
    projection = ObservationProjection(ignored_json_fields=frozenset({"requestId"}))
    real = normalize_http_response(
        httpx.Response(200, json={"name": "projects/p", "requestId": "real"}),
        projection=projection,
    )
    simulator = normalize_http_response(
        httpx.Response(200, json={"name": "projects/p", "requestId": "sim"}),
        projection=projection,
    )
    evidence = compare_observations(
        method_id="example:v1:projects.get",
        real=real,
        simulator=simulator,
        real_receipt="real-r",
        simulator_receipt="sim-r",
        projection=projection,
    )
    assert evidence.equivalent
    assert not evidence.mismatches
    assert evidence.coverage_record().disposition is CoverageDisposition.ALIVE

    changed = normalize_http_response(
        httpx.Response(200, json={"name": "projects/other", "requestId": "sim"}),
        projection=projection,
    )
    mismatch = compare_observations(
        method_id="example:v1:projects.get",
        real=real,
        simulator=changed,
        real_receipt="real-r",
        simulator_receipt="sim-r2",
        projection=projection,
    )
    assert not mismatch.equivalent
    assert mismatch.mismatches == ("body",)


def test_coverage_is_fail_closed_until_every_method_is_receipted_alive() -> None:
    census = _census()
    methods, schemas = flatten_discovery_document(_discovery_doc("example", "v1"))
    assert census.methods == methods
    assert census.schemas == schemas

    first = census.methods[0]
    partial = GcpCoverageReport.evaluate(census, [_alive_record(first.identity, 0)])
    assert not partial.exact
    assert partial.alive_methods == 1
    assert partial.unknown_methods == 1
    assert len(partial.missing_method_ids) == 1

    unreceipted = GcpCoverageReport.evaluate(
        census,
        [
            GcpCoverageRecord(
                method_id=method.identity,
                disposition=CoverageDisposition.ALIVE,
            )
            for method in census.methods
        ],
    )
    assert not unreceipted.exact
    assert unreceipted.partial_methods == len(census.methods)
    assert len(unreceipted.unreceipted_alive_method_ids) == len(census.methods)

    complete = GcpCoverageReport.evaluate(
        census,
        [_alive_record(method.identity, index) for index, method in enumerate(census.methods)],
    )
    assert complete.exact
    assert complete.unknown_methods == 0
    assert not complete.missing_method_ids


def test_duplicate_evidence_is_not_exact() -> None:
    census = _census()
    records = [
        _alive_record(method.identity, index)
        for index, method in enumerate(census.methods)
    ]
    records.append(records[0])
    report = GcpCoverageReport.evaluate(census, records)
    assert not report.exact
    assert report.duplicate_method_ids == (records[0].method_id,)


def test_rdf_projection_uses_public_vocabularies_and_abox_identifiers() -> None:
    census = _census()
    graph = build_contract_rdf(census)
    serialized = graph.serialize(format="turtle")
    assert "dcat:Catalog" in serialized
    assert "dcat:Dataset" in serialized
    assert "skos:Concept" in serialized
    assert "urn:gymact:gcp:" in serialized
