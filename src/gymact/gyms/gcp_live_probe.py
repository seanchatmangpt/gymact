"""Credentialed, receipt-first GCP empirical probe boundary.

This module is the real-GCP half of exact differential validation.  It accepts
fully constructed request cases, executes only Google API HTTPS endpoints,
normalizes externally observable responses through ``gcp_exact``, and emits a
BLAKE3 receipt that never contains the bearer token.

It deliberately does not discover credentials, infer production authority, or
generate mutation payloads. READ and DO remain separate: consequential cases
are REFUSED unless both an explicit ``allow_do`` decision and an authority
reference are present. Missing credentials are BLOCKED, not UNSUPPORTED.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Mapping
from urllib.parse import urlparse
import json

from blake3 import blake3
import httpx

from gymact.gyms.gcp_behavior import GcpBehaviorEffect
from gymact.gyms.gcp_exact import GcpObservation, ObservationProjection, normalize_http_response
from gymact.gyms.gcp_validation import GcpValidationEvidence

__all__ = [
    "GcpLiveProbeDisposition",
    "GcpLiveProbeRequest",
    "GcpLiveProbeResult",
    "execute_live_probe",
]


class GcpLiveProbeDisposition(StrEnum):
    ALIVE = "ALIVE"
    BLOCKED = "BLOCKED"
    REFUSED = "REFUSED"


_READ_EFFECTS = frozenset(
    {
        GcpBehaviorEffect.READ_ONE,
        GcpBehaviorEffect.READ_MANY,
        GcpBehaviorEffect.IAM_GET,
        GcpBehaviorEffect.IAM_TEST,
        GcpBehaviorEffect.OPERATION_GET,
        GcpBehaviorEffect.OPERATION_LIST,
        GcpBehaviorEffect.OPERATION_WAIT,
    }
)


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _request_digest(request: "GcpLiveProbeRequest") -> str:
    payload = {
        "case_id": request.case_id,
        "method_id": request.method_id,
        "effect": request.effect.value,
        "http_method": request.http_method,
        "url": request.url,
        "query": dict(sorted(request.query.items())),
        "body": request.body,
        "headers": tuple(sorted((key.lower(), value) for key, value in request.headers.items())),
    }
    return blake3(_canonical_json(payload).encode()).hexdigest()


def _receipt(
    *,
    request: "GcpLiveProbeRequest",
    disposition: GcpLiveProbeDisposition,
    observation: GcpObservation | None,
    reason: str | None,
) -> str:
    payload = {
        "case_id": request.case_id,
        "method_id": request.method_id,
        "effect": request.effect.value,
        "request_digest_blake3": _request_digest(request),
        "disposition": disposition.value,
        "observation_digest_blake3": observation.digest_blake3 if observation else None,
        "authority_ref": request.authority_ref,
        "reason": reason,
    }
    return f"gcp-live-probe:blake3:{blake3(_canonical_json(payload).encode()).hexdigest()}"


def _admitted_google_host(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname:
        return False
    hostname = parsed.hostname.lower()
    return hostname == "googleapis.com" or hostname.endswith(".googleapis.com")


@dataclass(frozen=True, slots=True)
class GcpLiveProbeRequest:
    case_id: str
    method_id: str
    effect: GcpBehaviorEffect
    http_method: str
    url: str
    query: Mapping[str, str] = field(default_factory=dict)
    body: Any = None
    headers: Mapping[str, str] = field(default_factory=dict)
    authority_ref: str | None = None

    def __post_init__(self) -> None:
        if not self.case_id:
            raise ValueError("GCP_LIVE_CASE_ID_REQUIRED")
        if not self.method_id:
            raise ValueError("GCP_LIVE_METHOD_ID_REQUIRED")
        if not self.http_method:
            raise ValueError("GCP_LIVE_HTTP_METHOD_REQUIRED")
        if not _admitted_google_host(self.url):
            raise ValueError("GCP_LIVE_ENDPOINT_NOT_GOOGLEAPIS_HTTPS")
        forbidden_headers = {name.lower() for name in self.headers} & {
            "authorization",
            "proxy-authorization",
            "cookie",
        }
        if forbidden_headers:
            raise ValueError("GCP_LIVE_CALLER_AUTH_HEADERS_REFUSED")

    @property
    def consequential(self) -> bool:
        return self.effect not in _READ_EFFECTS


@dataclass(frozen=True, slots=True)
class GcpLiveProbeResult:
    request: GcpLiveProbeRequest
    disposition: GcpLiveProbeDisposition
    observation: GcpObservation | None
    receipt: str
    reason: str | None = None

    @property
    def executed(self) -> bool:
        return self.disposition is GcpLiveProbeDisposition.ALIVE and self.observation is not None

    def pair_with_simulator(
        self,
        *,
        simulator_observation: GcpObservation | None,
        simulator_receipt: str | None,
    ) -> GcpValidationEvidence:
        if self.executed and simulator_observation is not None and simulator_receipt:
            standing = (
                "ALIVE"
                if self.observation is not None
                and self.observation.digest_blake3 == simulator_observation.digest_blake3
                else "PARTIAL_ALIVE"
            )
        elif self.disposition is GcpLiveProbeDisposition.REFUSED:
            standing = "REFUSED"
        else:
            standing = "BLOCKED"
        return GcpValidationEvidence(
            case_id=self.request.case_id,
            real_observation=self.observation,
            simulator_observation=simulator_observation,
            real_receipt=self.receipt if self.executed else None,
            simulator_receipt=simulator_receipt,
            standing=standing,
        )


def execute_live_probe(
    request: GcpLiveProbeRequest,
    *,
    access_token: str | None,
    allow_do: bool = False,
    client: httpx.Client | None = None,
    projection: ObservationProjection = ObservationProjection(),
    timeout: float = 60.0,
) -> GcpLiveProbeResult:
    """Execute exactly one admitted empirical request and preserve a receipt."""

    if request.consequential and not allow_do:
        reason = "LIVE_GCP_DO_NOT_ADMITTED"
        disposition = GcpLiveProbeDisposition.REFUSED
        return GcpLiveProbeResult(
            request=request,
            disposition=disposition,
            observation=None,
            receipt=_receipt(request=request, disposition=disposition, observation=None, reason=reason),
            reason=reason,
        )
    if request.consequential and not request.authority_ref:
        reason = "LIVE_GCP_AUTHORITY_REF_REQUIRED"
        disposition = GcpLiveProbeDisposition.REFUSED
        return GcpLiveProbeResult(
            request=request,
            disposition=disposition,
            observation=None,
            receipt=_receipt(request=request, disposition=disposition, observation=None, reason=reason),
            reason=reason,
        )
    if not access_token:
        reason = "GCP_ACCESS_TOKEN_UNAVAILABLE"
        disposition = GcpLiveProbeDisposition.BLOCKED
        return GcpLiveProbeResult(
            request=request,
            disposition=disposition,
            observation=None,
            receipt=_receipt(request=request, disposition=disposition, observation=None, reason=reason),
            reason=reason,
        )

    own_client = client is None
    http = client or httpx.Client(timeout=timeout, follow_redirects=False)
    try:
        headers = {
            "authorization": f"Bearer {access_token}",
            "accept": "application/json",
            "user-agent": "gymact-gcp-exact-probe/26.8.19",
            **{key: value for key, value in request.headers.items()},
        }
        response = http.request(
            request.http_method.upper(),
            request.url,
            params=dict(request.query),
            json=request.body if request.body is not None else None,
            headers=headers,
        )
        observation = normalize_http_response(response, projection=projection)
        disposition = GcpLiveProbeDisposition.ALIVE
        return GcpLiveProbeResult(
            request=request,
            disposition=disposition,
            observation=observation,
            receipt=_receipt(
                request=request,
                disposition=disposition,
                observation=observation,
                reason=None,
            ),
        )
    except (httpx.ConnectError, httpx.ReadError, httpx.RemoteProtocolError, httpx.TimeoutException) as exc:
        reason = f"GCP_TRANSPORT_BLOCKED:{type(exc).__name__}"
        disposition = GcpLiveProbeDisposition.BLOCKED
        return GcpLiveProbeResult(
            request=request,
            disposition=disposition,
            observation=None,
            receipt=_receipt(request=request, disposition=disposition, observation=None, reason=reason),
            reason=reason,
        )
    finally:
        if own_client:
            http.close()
