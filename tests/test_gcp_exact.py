from __future__ import annotations

import json

import httpx

from gymact.gyms.gcp_exact import (
    CoverageDisposition,
    GcpCoverageRecord,
    GcpCoverageReport,
    build_contract_rdf,
    flatten_discovery_document,
    load_discovery_census,
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


def test_flatten_discovery_document_recurses_and_hashes_schemas() -> None:
    methods, schemas = flatten_discovery_document(_discovery_doc("example", "v1"))

    assert [method.identity for method in methods] == [
        "example:v1:rootCall",
        "example:v1:projects.locations.get",
    ]
    nested = methods[1]
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


def test_coverage_is_fail_closed_until_every_method_is_alive() -> None:
    document = _discovery_doc("example", "v1")
    methods, schemas = flatten_discovery_document(document)
    directory = {
        "items": [
            {
                "name": "example",
                "version": "v1",
                "title": "Example",
                "preferred": True,
                "discoveryRestUrl": "https://example.test/discovery",
            }
        ]
    }

    def handler(request: httpx.Request) -> httpx.Response:
        if "discovery.googleapis.com" in str(request.url):
            return httpx.Response(200, json=directory)
        return httpx.Response(200, json=document)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    census = load_discovery_census(client=client)
    assert census.methods == methods
    assert census.schemas == schemas

    first = census.methods[0]
    partial = GcpCoverageReport.evaluate(
        census,
        [
            GcpCoverageRecord(
                method_id=first.identity,
                disposition=CoverageDisposition.ALIVE,
                real_receipt="real-1",
                simulator_receipt="sim-1",
            )
        ],
    )
    assert not partial.exact
    assert partial.alive_methods == 1
    assert partial.unknown_methods == 1
    assert len(partial.missing_method_ids) == 1

    complete = GcpCoverageReport.evaluate(
        census,
        [
            GcpCoverageRecord(
                method_id=method.identity,
                disposition=CoverageDisposition.ALIVE,
                real_receipt=f"real-{index}",
                simulator_receipt=f"sim-{index}",
            )
            for index, method in enumerate(census.methods)
        ],
    )
    assert complete.exact
    assert complete.unknown_methods == 0
    assert not complete.missing_method_ids


def test_rdf_projection_uses_public_vocabularies_and_abox_identifiers() -> None:
    document = _discovery_doc("example", "v1")
    methods, schemas = flatten_discovery_document(document)
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
        return httpx.Response(200, content=json.dumps(document).encode())

    client = httpx.Client(transport=httpx.MockTransport(handler))
    census = load_discovery_census(client=client)
    assert census.methods == methods
    assert census.schemas == schemas

    graph = build_contract_rdf(census)
    serialized = graph.serialize(format="turtle")
    assert "dcat:Catalog" in serialized
    assert "dcat:Dataset" in serialized
    assert "skos:Concept" in serialized
    assert "urn:gymact:gcp:" in serialized
