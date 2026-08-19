"""Resilient live Google Discovery census.

Google's Discovery directory is itself an observed contract. Individual entries
can become stale before the directory is updated. Stable 404/410 responses are
preserved as unavailable contract observations; transient transport/5xx/429
failures receive bounded retry and are preserved as typed unavailable evidence
when exhausted so one failed edge cannot erase the rest of the census.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import time
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
_TRANSIENT_STATUS = {408, 429, 500, 502, 503, 504}


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _get_with_retry(
    http: httpx.Client,
    url: str,
    *,
    attempts: int = 4,
    base_delay: float = 0.25,
) -> httpx.Response:
    """Retry only failures that do not establish contract absence."""
    last_error: httpx.HTTPError | None = None
    for attempt in range(attempts):
        try:
            response = http.get(url)
        except (httpx.ConnectError, httpx.ReadError, httpx.RemoteProtocolError) as exc:
            last_error = exc
            if attempt + 1 == attempts:
                raise
            time.sleep(base_delay * (2**attempt))
            continue
        if response.status_code not in _TRANSIENT_STATUS or attempt + 1 == attempts:
            return response
        time.sleep(base_delay * (2**attempt))
    if last_error is not None:
        raise last_error
    raise RuntimeError("DISCOVERY_RETRY_EXHAUSTED_WITHOUT_RESPONSE")


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


def _transport_failure_digest(discovery_url: str, exc: httpx.HTTPError) -> str:
    """Digest stable transport-failure identity without volatile exception text."""
    payload = f"{type(exc).__name__}:{discovery_url}".encode()
    return blake3(payload).hexdigest()


def load_resilient_discovery_census(
    *,
    client: httpx.Client | None = None,
    include_nonpreferred: bool = True,
    timeout: float = 60.0,
) -> ResilientDiscoveryCensus:
    """Probe every advertised Discovery entry and preserve all unavailability."""
    own_client = client is None
    http = client or httpx.Client(timeout=timeout, follow_redirects=True)
    try:
        response = _get_with_retry(http, _DISCOVERY_DIRECTORY)
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
            try:
                doc_response = _get_with_retry(http, discovery_url)
            except (httpx.ConnectError, httpx.ReadError, httpx.RemoteProtocolError) as exc:
                unavailable.append(
                    DiscoveryUnavailable(
                        name=str(item["name"]),
                        version=str(item["version"]),
                        discovery_url=discovery_url,
                        status_code=0,
                        response_digest_blake3=_transport_failure_digest(discovery_url, exc),
                        reason="ADVERTISED_DISCOVERY_TRANSPORT_EXHAUSTED",
                    )
                )
                continue

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

            if doc_response.status_code in _TRANSIENT_STATUS:
                unavailable.append(
                    DiscoveryUnavailable(
                        name=str(item["name"]),
                        version=str(item["version"]),
                        discovery_url=discovery_url,
                        status_code=doc_response.status_code,
                        response_digest_blake3=blake3(doc_response.content).hexdigest(),
                        reason="ADVERTISED_DISCOVERY_TRANSIENT_EXHAUSTED",
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
