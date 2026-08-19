"""GCP exactness as a falsifiable, evidence-bounded conformance contract.

This module deliberately does not claim to reproduce Google's private backend.
It defines the externally observable surface GymAct can prove equivalent:
Google-published API discovery contracts plus receipted differential observations
against a real GCP project.

The core law is:

    simulator exactness == complete admitted contract coverage
                          + observed behavioral equivalence
                          + zero silent exclusions

Anything not published or not empirically observed remains UNKNOWN.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from hashlib import sha256
import json
from typing import Any, Iterable, Mapping

import httpx
from rdflib import DCTERMS, RDF, URIRef, Graph, Literal, Namespace
from rdflib.namespace import DCAT, SKOS

__all__ = [
    "CoverageDisposition",
    "DiscoveryApi",
    "DiscoveryMethod",
    "DiscoverySchema",
    "GcpContractCensus",
    "GcpCoverageRecord",
    "GcpCoverageReport",
    "build_contract_rdf",
    "flatten_discovery_document",
    "load_discovery_census",
]

_DISCOVERY_DIRECTORY = "https://discovery.googleapis.com/discovery/v1/apis"
_GCP = Namespace("urn:gymact:gcp:")


class CoverageDisposition(StrEnum):
    """Standing of one externally observable GCP contract unit."""

    UNKNOWN = "UNKNOWN"
    PARTIAL_ALIVE = "PARTIAL_ALIVE"
    ALIVE = "ALIVE"
    BLOCKED = "BLOCKED"
    UNSUPPORTED = "UNSUPPORTED"
    REFUSED = "REFUSED"


@dataclass(frozen=True, slots=True)
class DiscoveryApi:
    name: str
    version: str
    title: str
    preferred: bool
    discovery_url: str
    documentation_url: str | None = None
    labels: tuple[str, ...] = ()

    @property
    def identity(self) -> str:
        return f"{self.name}:{self.version}"


@dataclass(frozen=True, slots=True)
class DiscoveryMethod:
    api: str
    version: str
    resource_path: str
    name: str
    http_method: str
    path: str
    request_schema: str | None
    response_schema: str | None
    scopes: tuple[str, ...]
    description: str | None = None

    @property
    def identity(self) -> str:
        prefix = f"{self.api}:{self.version}"
        resource = f"{self.resource_path}." if self.resource_path else ""
        return f"{prefix}:{resource}{self.name}"


@dataclass(frozen=True, slots=True)
class DiscoverySchema:
    api: str
    version: str
    name: str
    canonical_json: str
    digest_sha256: str

    @property
    def identity(self) -> str:
        return f"{self.api}:{self.version}:schema:{self.name}"


@dataclass(frozen=True, slots=True)
class GcpContractCensus:
    apis: tuple[DiscoveryApi, ...]
    methods: tuple[DiscoveryMethod, ...]
    schemas: tuple[DiscoverySchema, ...]
    directory_digest_sha256: str

    @property
    def method_ids(self) -> frozenset[str]:
        return frozenset(method.identity for method in self.methods)


@dataclass(frozen=True, slots=True)
class GcpCoverageRecord:
    method_id: str
    disposition: CoverageDisposition
    real_receipt: str | None = None
    simulator_receipt: str | None = None
    evidence_digest: str | None = None
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class GcpCoverageReport:
    admitted_methods: int
    alive_methods: int
    partial_methods: int
    unknown_methods: int
    blocked_methods: int
    unsupported_methods: int
    refused_methods: int
    missing_method_ids: tuple[str, ...] = field(default_factory=tuple)
    extra_method_ids: tuple[str, ...] = field(default_factory=tuple)

    @property
    def exact(self) -> bool:
        return (
            self.admitted_methods > 0
            and self.alive_methods == self.admitted_methods
            and not self.missing_method_ids
            and not self.extra_method_ids
            and self.partial_methods == 0
            and self.unknown_methods == 0
            and self.blocked_methods == 0
            and self.unsupported_methods == 0
            and self.refused_methods == 0
        )

    @classmethod
    def evaluate(
        cls,
        census: GcpContractCensus,
        records: Iterable[GcpCoverageRecord],
    ) -> "GcpCoverageReport":
        by_id = {record.method_id: record for record in records}
        admitted = census.method_ids
        observed = frozenset(by_id)
        missing = tuple(sorted(admitted - observed))
        extra = tuple(sorted(observed - admitted))

        counts = {disposition: 0 for disposition in CoverageDisposition}
        for method_id in admitted:
            record = by_id.get(method_id)
            disposition = record.disposition if record else CoverageDisposition.UNKNOWN
            counts[disposition] += 1

        return cls(
            admitted_methods=len(admitted),
            alive_methods=counts[CoverageDisposition.ALIVE],
            partial_methods=counts[CoverageDisposition.PARTIAL_ALIVE],
            unknown_methods=counts[CoverageDisposition.UNKNOWN],
            blocked_methods=counts[CoverageDisposition.BLOCKED],
            unsupported_methods=counts[CoverageDisposition.UNSUPPORTED],
            refused_methods=counts[CoverageDisposition.REFUSED],
            missing_method_ids=missing,
            extra_method_ids=extra,
        )


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _schema_ref(value: Mapping[str, Any] | None) -> str | None:
    if not value:
        return None
    ref = value.get("$ref")
    return str(ref) if ref is not None else None


def _walk_resources(
    *,
    api: str,
    version: str,
    resources: Mapping[str, Any],
    prefix: str = "",
) -> list[DiscoveryMethod]:
    methods: list[DiscoveryMethod] = []
    for resource_name, resource in sorted(resources.items()):
        resource_path = f"{prefix}.{resource_name}" if prefix else resource_name
        for method_name, method in sorted(resource.get("methods", {}).items()):
            scopes = tuple(sorted(str(scope) for scope in method.get("scopes", ())))
            methods.append(
                DiscoveryMethod(
                    api=api,
                    version=version,
                    resource_path=resource_path,
                    name=method_name,
                    http_method=str(method.get("httpMethod", "")),
                    path=str(method.get("path", "")),
                    request_schema=_schema_ref(method.get("request")),
                    response_schema=_schema_ref(method.get("response")),
                    scopes=scopes,
                    description=method.get("description"),
                )
            )
        methods.extend(
            _walk_resources(
                api=api,
                version=version,
                resources=resource.get("resources", {}),
                prefix=resource_path,
            )
        )
    return methods


def flatten_discovery_document(document: Mapping[str, Any]) -> tuple[tuple[DiscoveryMethod, ...], tuple[DiscoverySchema, ...]]:
    """Flatten one Google Discovery document into deterministic contract units."""
    api = str(document["name"])
    version = str(document["version"])
    methods: list[DiscoveryMethod] = []

    for method_name, method in sorted(document.get("methods", {}).items()):
        methods.append(
            DiscoveryMethod(
                api=api,
                version=version,
                resource_path="",
                name=method_name,
                http_method=str(method.get("httpMethod", "")),
                path=str(method.get("path", "")),
                request_schema=_schema_ref(method.get("request")),
                response_schema=_schema_ref(method.get("response")),
                scopes=tuple(sorted(str(scope) for scope in method.get("scopes", ()))),
                description=method.get("description"),
            )
        )
    methods.extend(
        _walk_resources(
            api=api,
            version=version,
            resources=document.get("resources", {}),
        )
    )

    schemas: list[DiscoverySchema] = []
    for name, schema in sorted(document.get("schemas", {}).items()):
        canonical = _canonical_json(schema)
        schemas.append(
            DiscoverySchema(
                api=api,
                version=version,
                name=name,
                canonical_json=canonical,
                digest_sha256=sha256(canonical.encode()).hexdigest(),
            )
        )
    return tuple(methods), tuple(schemas)


def load_discovery_census(
    *,
    client: httpx.Client | None = None,
    include_nonpreferred: bool = True,
    timeout: float = 60.0,
) -> GcpContractCensus:
    """Load every API/version currently published by Google Discovery.

    This is intentionally live and credential-free. Network failure is an execution
    blocker; callers must not replace it with a fabricated static catalog.
    """
    own_client = client is None
    http = client or httpx.Client(timeout=timeout, follow_redirects=True)
    try:
        response = http.get(_DISCOVERY_DIRECTORY)
        response.raise_for_status()
        directory = response.json()
        canonical_directory = _canonical_json(directory)

        apis: list[DiscoveryApi] = []
        methods: list[DiscoveryMethod] = []
        schemas: list[DiscoverySchema] = []
        for item in directory.get("items", []):
            if not include_nonpreferred and not bool(item.get("preferred")):
                continue
            discovery_url = str(item["discoveryRestUrl"])
            api = DiscoveryApi(
                name=str(item["name"]),
                version=str(item["version"]),
                title=str(item.get("title", item["name"])),
                preferred=bool(item.get("preferred")),
                discovery_url=discovery_url,
                documentation_url=item.get("documentationLink"),
                labels=tuple(sorted(str(label) for label in item.get("labels", ()))),
            )
            doc_response = http.get(discovery_url)
            doc_response.raise_for_status()
            doc_methods, doc_schemas = flatten_discovery_document(doc_response.json())
            apis.append(api)
            methods.extend(doc_methods)
            schemas.extend(doc_schemas)

        return GcpContractCensus(
            apis=tuple(sorted(apis, key=lambda value: value.identity)),
            methods=tuple(sorted(methods, key=lambda value: value.identity)),
            schemas=tuple(sorted(schemas, key=lambda value: value.identity)),
            directory_digest_sha256=sha256(canonical_directory.encode()).hexdigest(),
        )
    finally:
        if own_client:
            http.close()


def build_contract_rdf(census: GcpContractCensus) -> Graph:
    """Project the census to RDF using public vocabularies only.

    `urn:gymact:gcp:*` values are ABox identities, never GymAct-owned TBox terms.
    """
    graph = Graph()
    graph.bind("dcat", DCAT)
    graph.bind("dcterms", DCTERMS)
    graph.bind("skos", SKOS)

    catalog = URIRef(_GCP["discovery-catalog"])
    graph.add((catalog, RDF.type, DCAT.Catalog))
    graph.add((catalog, DCTERMS.identifier, Literal(census.directory_digest_sha256)))

    for api in census.apis:
        api_ref = URIRef(_GCP[f"api/{api.name}/{api.version}"])
        graph.add((api_ref, RDF.type, DCAT.Dataset))
        graph.add((api_ref, DCTERMS.identifier, Literal(api.identity)))
        graph.add((api_ref, DCTERMS.title, Literal(api.title)))
        graph.add((catalog, DCAT.dataset, api_ref))
        if api.documentation_url:
            graph.add((api_ref, DCAT.landingPage, URIRef(api.documentation_url)))

    for method in census.methods:
        method_ref = URIRef(_GCP[f"method/{sha256(method.identity.encode()).hexdigest()}"])
        graph.add((method_ref, RDF.type, SKOS.Concept))
        graph.add((method_ref, SKOS.prefLabel, Literal(method.identity)))
        graph.add((method_ref, DCTERMS.identifier, Literal(method.identity)))
        graph.add((method_ref, DCTERMS.format, Literal(method.http_method)))

    return graph
