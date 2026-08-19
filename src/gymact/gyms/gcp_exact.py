"""Evidence-bounded GCP contract census and differential conformance.

"Exact GCP" means equality over an admitted externally observable projection.
Private Google implementation details are outside the claim. Unpublished or
unobserved behavior remains UNKNOWN and can never be silently promoted.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from hashlib import sha256
import json
from typing import Any, Iterable, Mapping

from blake3 import blake3
import httpx
from rdflib import DCTERMS, RDF, Graph, Literal, Namespace, URIRef
from rdflib.namespace import DCAT, SKOS

__all__ = [
    "CoverageDisposition",
    "DiscoveryApi",
    "DiscoveryMethod",
    "DiscoverySchema",
    "GcpContractCensus",
    "GcpCoverageRecord",
    "GcpCoverageReport",
    "GcpDifferentialEvidence",
    "GcpObservation",
    "ObservationProjection",
    "build_contract_rdf",
    "compare_observations",
    "flatten_discovery_document",
    "load_discovery_census",
    "normalize_http_response",
]

_DISCOVERY_DIRECTORY = "https://discovery.googleapis.com/discovery/v1/apis"
_GCP = Namespace("urn:gymact:gcp:")
_DEFAULT_HEADERS = ("content-type", "etag", "location", "retry-after")


class CoverageDisposition(StrEnum):
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

    @property
    def contract_digest_blake3(self) -> str:
        payload = {
            "directory_sha256": self.directory_digest_sha256,
            "apis": [api.identity for api in self.apis],
            "methods": [
                {
                    "id": method.identity,
                    "verb": method.http_method,
                    "path": method.path,
                    "request": method.request_schema,
                    "response": method.response_schema,
                    "scopes": method.scopes,
                }
                for method in self.methods
            ],
            "schemas": [
                {"id": schema.identity, "sha256": schema.digest_sha256}
                for schema in self.schemas
            ],
        }
        return blake3(_canonical_json(payload).encode()).hexdigest()


@dataclass(frozen=True, slots=True)
class ObservationProjection:
    """Declared comparison boundary for a real/simulator observation pair."""

    headers: tuple[str, ...] = _DEFAULT_HEADERS
    ignored_json_fields: frozenset[str] = frozenset()


@dataclass(frozen=True, slots=True)
class GcpObservation:
    status_code: int
    headers: tuple[tuple[str, str], ...]
    body_kind: str
    canonical_body: str
    digest_blake3: str


@dataclass(frozen=True, slots=True)
class GcpDifferentialEvidence:
    method_id: str
    real: GcpObservation
    simulator: GcpObservation
    real_receipt: str
    simulator_receipt: str
    projection_digest_blake3: str
    evidence_digest_blake3: str
    equivalent: bool
    mismatches: tuple[str, ...]

    def coverage_record(self) -> "GcpCoverageRecord":
        disposition = (
            CoverageDisposition.ALIVE
            if self.equivalent
            else CoverageDisposition.PARTIAL_ALIVE
        )
        return GcpCoverageRecord(
            method_id=self.method_id,
            disposition=disposition,
            real_receipt=self.real_receipt,
            simulator_receipt=self.simulator_receipt,
            evidence_digest=self.evidence_digest_blake3,
            reason=None if self.equivalent else ";".join(self.mismatches),
        )


@dataclass(frozen=True, slots=True)
class GcpCoverageRecord:
    method_id: str
    disposition: CoverageDisposition
    real_receipt: str | None = None
    simulator_receipt: str | None = None
    evidence_digest: str | None = None
    reason: str | None = None

    @property
    def has_paired_evidence(self) -> bool:
        return bool(self.real_receipt and self.simulator_receipt and self.evidence_digest)


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
    duplicate_method_ids: tuple[str, ...] = field(default_factory=tuple)
    unreceipted_alive_method_ids: tuple[str, ...] = field(default_factory=tuple)

    @property
    def exact(self) -> bool:
        return (
            self.admitted_methods > 0
            and self.alive_methods == self.admitted_methods
            and not self.missing_method_ids
            and not self.extra_method_ids
            and not self.duplicate_method_ids
            and not self.unreceipted_alive_method_ids
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
        records_list = list(records)
        counts_by_id: dict[str, int] = {}
        by_id: dict[str, GcpCoverageRecord] = {}
        for record in records_list:
            counts_by_id[record.method_id] = counts_by_id.get(record.method_id, 0) + 1
            by_id[record.method_id] = record

        admitted = census.method_ids
        observed = frozenset(by_id)
        missing = tuple(sorted(admitted - observed))
        extra = tuple(sorted(observed - admitted))
        duplicates = tuple(sorted(key for key, count in counts_by_id.items() if count > 1))
        unreceipted = tuple(
            sorted(
                method_id
                for method_id in admitted
                if (record := by_id.get(method_id)) is not None
                and record.disposition is CoverageDisposition.ALIVE
                and not record.has_paired_evidence
            )
        )

        counts = {disposition: 0 for disposition in CoverageDisposition}
        for method_id in admitted:
            record = by_id.get(method_id)
            if record is None:
                disposition = CoverageDisposition.UNKNOWN
            elif (
                record.disposition is CoverageDisposition.ALIVE
                and not record.has_paired_evidence
            ):
                disposition = CoverageDisposition.PARTIAL_ALIVE
            else:
                disposition = record.disposition
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
            duplicate_method_ids=duplicates,
            unreceipted_alive_method_ids=unreceipted,
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
                    scopes=tuple(sorted(str(scope) for scope in method.get("scopes", ()))),
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


def flatten_discovery_document(
    document: Mapping[str, Any],
) -> tuple[tuple[DiscoveryMethod, ...], tuple[DiscoverySchema, ...]]:
    """Flatten one Google Discovery document into deterministic units."""
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

    return (
        tuple(sorted(methods, key=lambda value: value.identity)),
        tuple(sorted(schemas, key=lambda value: value.identity)),
    )


def load_discovery_census(
    *,
    client: httpx.Client | None = None,
    include_nonpreferred: bool = True,
    timeout: float = 60.0,
) -> GcpContractCensus:
    """Load every API/version currently published by Google Discovery."""
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


def _project_json(value: Any, ignored_fields: frozenset[str]) -> Any:
    if isinstance(value, dict):
        return {
            key: _project_json(item, ignored_fields)
            for key, item in sorted(value.items())
            if key not in ignored_fields
        }
    if isinstance(value, list):
        return [_project_json(item, ignored_fields) for item in value]
    return value


def normalize_http_response(
    response: httpx.Response,
    *,
    projection: ObservationProjection = ObservationProjection(),
) -> GcpObservation:
    """Normalize one externally visible HTTP result for deterministic comparison."""
    selected_headers = tuple(
        sorted(
            (name.lower(), response.headers[name])
            for name in projection.headers
            if name in response.headers
        )
    )
    raw = response.content
    if not raw:
        body_kind = "empty"
        canonical_body = ""
    else:
        try:
            decoded = response.json()
        except (json.JSONDecodeError, UnicodeDecodeError):
            body_kind = "bytes"
            canonical_body = raw.hex()
        else:
            body_kind = "json"
            canonical_body = _canonical_json(
                _project_json(decoded, projection.ignored_json_fields)
            )

    payload = {
        "status_code": response.status_code,
        "headers": selected_headers,
        "body_kind": body_kind,
        "canonical_body": canonical_body,
    }
    return GcpObservation(
        status_code=response.status_code,
        headers=selected_headers,
        body_kind=body_kind,
        canonical_body=canonical_body,
        digest_blake3=blake3(_canonical_json(payload).encode()).hexdigest(),
    )


def compare_observations(
    *,
    method_id: str,
    real: GcpObservation,
    simulator: GcpObservation,
    real_receipt: str,
    simulator_receipt: str,
    projection: ObservationProjection = ObservationProjection(),
) -> GcpDifferentialEvidence:
    """Compare a paired real-GCP/simulator observation and manufacture evidence."""
    mismatches: list[str] = []
    if real.status_code != simulator.status_code:
        mismatches.append("status_code")
    if real.headers != simulator.headers:
        mismatches.append("headers")
    if real.body_kind != simulator.body_kind:
        mismatches.append("body_kind")
    if real.canonical_body != simulator.canonical_body:
        mismatches.append("body")

    projection_payload = {
        "headers": projection.headers,
        "ignored_json_fields": sorted(projection.ignored_json_fields),
    }
    projection_digest = blake3(_canonical_json(projection_payload).encode()).hexdigest()
    evidence_payload = {
        "method_id": method_id,
        "real_digest": real.digest_blake3,
        "simulator_digest": simulator.digest_blake3,
        "real_receipt": real_receipt,
        "simulator_receipt": simulator_receipt,
        "projection_digest": projection_digest,
        "mismatches": mismatches,
    }
    evidence_digest = blake3(_canonical_json(evidence_payload).encode()).hexdigest()
    return GcpDifferentialEvidence(
        method_id=method_id,
        real=real,
        simulator=simulator,
        real_receipt=real_receipt,
        simulator_receipt=simulator_receipt,
        projection_digest_blake3=projection_digest,
        evidence_digest_blake3=evidence_digest,
        equivalent=not mismatches,
        mismatches=tuple(mismatches),
    )


def build_contract_rdf(census: GcpContractCensus) -> Graph:
    """Project the census to RDF using public vocabularies only."""
    graph = Graph()
    graph.bind("dcat", DCAT)
    graph.bind("dcterms", DCTERMS)
    graph.bind("skos", SKOS)

    catalog = URIRef(_GCP["discovery-catalog"])
    graph.add((catalog, RDF.type, DCAT.Catalog))
    graph.add((catalog, DCTERMS.identifier, Literal(census.contract_digest_blake3)))

    api_refs: dict[str, URIRef] = {}
    for api in census.apis:
        api_ref = URIRef(_GCP[f"api/{api.name}/{api.version}"])
        api_refs[api.identity] = api_ref
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
        api_ref = api_refs.get(f"{method.api}:{method.version}")
        if api_ref is not None:
            graph.add((method_ref, SKOS.inScheme, api_ref))

    return graph
