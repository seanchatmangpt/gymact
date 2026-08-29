from __future__ import annotations

import httpx
import pytest

from gymact.gyms.gcp_behavior import GcpBehaviorEffect
from gymact.gyms.gcp_exact import normalize_http_response
from gymact.gyms.gcp_live_probe import (
    GcpLiveProbeDisposition,
    GcpLiveProbeRequest,
    execute_live_probe,
)


def test_read_probe_executes_real_http_transport_and_never_receipts_token() -> None:
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["authorization"] = request.headers["authorization"]
        assert str(request.url) == "https://compute.googleapis.com/compute/v1/projects/p/zones/z/instances/i"
        return httpx.Response(
            200,
            headers={"content-type": "application/json", "etag": "abc"},
            json={"name": "i", "status": "RUNNING"},
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    request = GcpLiveProbeRequest(
        case_id="compute:v1:instances.get#HAPPY_PATH",
        method_id="compute:v1:instances.get",
        effect=GcpBehaviorEffect.READ_ONE,
        http_method="GET",
        url="https://compute.googleapis.com/compute/v1/projects/p/zones/z/instances/i",
    )
    result = execute_live_probe(request, access_token="super-secret-token", client=client)
    assert result.disposition is GcpLiveProbeDisposition.ALIVE
    assert result.executed
    assert result.observation is not None
    assert result.observation.status_code == 200
    assert seen["authorization"] == "Bearer super-secret-token"
    assert "super-secret-token" not in result.receipt
    assert result.receipt.startswith("gcp-live-probe:blake3:")


def test_missing_token_is_blocked_without_transport_execution() -> None:
    called = False

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal called
        called = True
        return httpx.Response(500)

    request = GcpLiveProbeRequest(
        case_id="compute:v1:instances.get#HAPPY_PATH",
        method_id="compute:v1:instances.get",
        effect=GcpBehaviorEffect.READ_ONE,
        http_method="GET",
        url="https://compute.googleapis.com/compute/v1/projects/p/zones/z/instances/i",
    )
    client = httpx.Client(transport=httpx.MockTransport(handler))
    result = execute_live_probe(request, access_token=None, client=client)
    assert result.disposition is GcpLiveProbeDisposition.BLOCKED
    assert result.reason == "GCP_ACCESS_TOKEN_UNAVAILABLE"
    assert called is False


def test_do_probe_refuses_without_both_explicit_do_and_authority() -> None:
    request = GcpLiveProbeRequest(
        case_id="compute:v1:instances.insert#HAPPY_PATH",
        method_id="compute:v1:instances.insert",
        effect=GcpBehaviorEffect.CREATE,
        http_method="POST",
        url="https://compute.googleapis.com/compute/v1/projects/p/zones/z/instances",
        body={"name": "test"},
    )
    result = execute_live_probe(request, access_token="token", allow_do=False)
    assert result.disposition is GcpLiveProbeDisposition.REFUSED
    assert result.reason == "LIVE_GCP_DO_NOT_ADMITTED"

    result = execute_live_probe(request, access_token="token", allow_do=True)
    assert result.disposition is GcpLiveProbeDisposition.REFUSED
    assert result.reason == "LIVE_GCP_AUTHORITY_REF_REQUIRED"


def test_do_probe_executes_only_after_explicit_authority() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        return httpx.Response(200, headers={"content-type": "application/json"}, json={"name": "i"})

    request = GcpLiveProbeRequest(
        case_id="compute:v1:instances.insert#HAPPY_PATH",
        method_id="compute:v1:instances.insert",
        effect=GcpBehaviorEffect.CREATE,
        http_method="POST",
        url="https://compute.googleapis.com/compute/v1/projects/p/zones/z/instances",
        body={"name": "i"},
        authority_ref="urn:test:gcp:authority",
    )
    client = httpx.Client(transport=httpx.MockTransport(handler))
    result = execute_live_probe(request, access_token="token", allow_do=True, client=client)
    assert result.executed
    assert result.observation is not None
    assert result.observation.status_code == 200


def test_non_google_endpoint_and_caller_auth_headers_are_refused_at_construction() -> None:
    with pytest.raises(ValueError, match="GCP_LIVE_ENDPOINT_NOT_GOOGLEAPIS_HTTPS"):
        GcpLiveProbeRequest(
            case_id="x#HAPPY_PATH",
            method_id="x",
            effect=GcpBehaviorEffect.READ_ONE,
            http_method="GET",
            url="https://example.com/not-gcp",
        )

    with pytest.raises(ValueError, match="GCP_LIVE_CALLER_AUTH_HEADERS_REFUSED"):
        GcpLiveProbeRequest(
            case_id="x#HAPPY_PATH",
            method_id="x",
            effect=GcpBehaviorEffect.READ_ONE,
            http_method="GET",
            url="https://example.googleapis.com/v1/x",
            headers={"Authorization": "caller-token"},
        )


def test_pairing_manufactures_case_level_standing_from_real_and_sim_receipts() -> None:
    response = httpx.Response(
        200,
        headers={"content-type": "application/json"},
        json={"name": "same"},
    )
    simulator = normalize_http_response(response)

    def handler(request: httpx.Request) -> httpx.Response:
        return response

    request = GcpLiveProbeRequest(
        case_id="example:v1:widgets.get#HAPPY_PATH",
        method_id="example:v1:widgets.get",
        effect=GcpBehaviorEffect.READ_ONE,
        http_method="GET",
        url="https://example.googleapis.com/v1/widgets/w",
    )
    client = httpx.Client(transport=httpx.MockTransport(handler))
    real = execute_live_probe(request, access_token="token", client=client)
    evidence = real.pair_with_simulator(
        simulator_observation=simulator,
        simulator_receipt="simulator:receipt",
    )
    assert evidence.standing == "ALIVE"
    assert evidence.paired
    assert evidence.equivalent

    divergent = normalize_http_response(
        httpx.Response(404, headers={"content-type": "application/json"}, json={"error": "missing"})
    )
    evidence = real.pair_with_simulator(
        simulator_observation=divergent,
        simulator_receipt="simulator:receipt",
    )
    assert evidence.standing == "PARTIAL_ALIVE"
    assert evidence.paired
    assert not evidence.equivalent
