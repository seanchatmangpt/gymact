"""Resilient live Google Discovery census.

Google's Discovery directory is itself an observed contract. Individual entries
can become stale before the directory is updated. A stale advertised document
must be preserved as evidence, not crash the census and not silently vanish.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Any

from blake3 import blake3
import httpx

from gymact.gyms.gcp_exact import (
    DiscoveryApi,
    DiscoveryMethod,
    DiscoverySchema,
    GcpContractCensus,
    flatten_discovery_document,
)

__all__ = [
    "DiscoveryUnavailable",
    "ResilientDiscoveryCensus",
    "load_resilient_discovery_census",
]

_DISCOVERY_DIRECTORY = "https://discovery.googleapis.com/discovery/v1/apis"


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


@dataclass(frozen=True, slots=True)
class DiscoveryUnavailable:
    name: str
    version: str
    discovery_url: str
    status_code: int
    response_digest_blake3: str
    reason: str

    @property
    def identity(self) -> str:
        return f"{self.name}:{self.version}"


@dataclass(frozen=True, slots=True)
class ResilientDiscoveryCensus:
    census: GcpContractCensus
    unavailable: tuple[DiscoveryUnavailable, ...]
    advertised_entries: int

    @property
    def probed_entries(self) -> int:
        return len(self.census.apis) + len(self.unavailable)

    @property
    def complete_probe(self) -> bool:
        return self.advertised_entries > 0 and self.probed_entries == self.advertised_entries

    @property
    def receipt_digest_blake3(self) -> str:
        payload = {
            "contract": self.census.contract_digest_blake3,
            "advertised": self.advertised_entries,
            "available": [api.identity for api in self.census.apis],
            "unavailable": [
                {
                    "id": item.identity,
                    "url": item.discovery_url,
                    "status": item.status_code,
                    "digest": item.response_digest_blake3,
                    "reason": item.reason,
                }
                for item in self.unavailable
            ],
        }
        return blake3(_canonical_json(payload).encode()).hexdigest()


def load_resilient_discovery_census(
    *,
    client: httpx.Client | None = None,
    include_nonpreferred: bool = True,
    timeout: float = 60.0,
) -> ResilientDiscoveryCensus:
    """Probe every advertised Discovery entry and preserve stable unavailability.

    HTTP 404/410 means the directory advertises a document that is no longer
    available. Those entries are retained as explicit observations. Other HTTP
    failures remain execution failures because they can represent transient or
    authorization/network problems and therefore cannot be reclassified as
    absent contracts.
    """
    own_client = client is None
    http = client or httpx.Client(timeout=timeout, follow_redirects=True)
    try:
        response = http.get(_DISCOVERY_DIRECTORY)
        response.raise_for_status()
        directory = response.json()
        canonical_directory = _canonical_json(directory)

        selected = [
            item
            for item in directory.get("items", [])
            if include_nonpreferred or bool(item.get("preferred"))
        ]
        apis: list[DiscoveryApi] = []
        methods: list[DiscoveryMethod] = []
        schemas: list[DiscoverySchema] = []
        unavailable: list[DiscoveryUnavailable] = []

        for item in selected:
            discovery_url = str(item["discoveryRestUrl"])
            doc_response = http.get(discovery_url)
            if doc_response.status_code in {404, 410}:
                unavailable.append(
                    DiscoveryUnavailable(
                        name=str(item["name"]),
                        version=str(item["version"]),
                        discovery_url=discovery_url,
                        status_code=doc_response.status_code,
                        response_digest_blake3=blake3(doc_response.content).hexdigest(),
                        reason="ADVERTISED_DISCOVERY_DOCUMENT_UNAVAILABLE",
                    )
                )
                continue
            doc_response.raise_for_status()

            api = DiscoveryApi(
                name=str(item["name"]),
                version=str(item["version"]),
                title=str(item.get("title", item["name"])),
                preferred=bool(item.get("preferred")),
                discovery_url=discovery_url,
                documentation_url=item.get("documentationLink"),
                labels=tuple(sorted(str(label) for label in item.get("labels", ()))),
            )
            doc_methods, doc_schemas = flatten_discovery_document(doc_response.json())
            apis.append(api)
            methods.extend(doc_methods)
            schemas.extend(doc_schemas)

        census = GcpContractCensus(
            apis=tuple(sorted(apis, key=lambda value: value.identity)),
            methods=tuple(sorted(methods, key=lambda value: value.identity)),
            schemas=tuple(sorted(schemas, key=lambda value: value.identity)),
            directory_digest_sha256=sha256(canonical_directory.encode()).hexdigest(),
        )
        return ResilientDiscoveryCensus(
            census=census,
            unavailable=tuple(sorted(unavailable, key=lambda value: value.identity)),
            advertised_entries=len(selected),
        )
    finally:
        if own_client:
            http.close()
