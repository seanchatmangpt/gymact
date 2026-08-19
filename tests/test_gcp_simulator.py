from __future__ import annotations

from blake3 import blake3
import pytest

from gymact import ActuationIntent, GymAct, MaterializationIntent
from gymact.gyms.gcp_behavior import (
    GcpBehaviorEffect,
    compile_behavior_corpus,
    compile_behavior_rule,
)
from gymact.gyms.gcp_exact import DiscoveryMethod, GcpContractCensus
from gymact.gyms.gcp_simulator import (
    GCP_ADVANCE_CLOCK_CAPABILITY,
    GCP_INVOKE_CAPABILITY,
    GCP_QUERY_CAPABILITY,
    GcpExactSimulator,
    GcpExactSimulatorEnvironment,
    GcpReplayFixture,
    GcpSimulatedResponse,
    canonical_request_digest,
)


def _method(
    name: str,
    verb: str,
    *,
    resource: str = "widgets",
    path: str | None = None,
    response: str | None = "Widget",
) -> DiscoveryMethod:
    return DiscoveryMethod(
        api="example",
        version="v1",
        resource_path=resource,
        name=name,
        http_method=verb,
        path=path or f"v1/{{+name}}:{name}",
        request_schema="Widget" if verb != "GET" else None,
        response_schema=response,
        scopes=("https://www.googleapis.com/auth/cloud-platform",),
    )


def _config(methods: tuple[DiscoveryMethod, ...]) -> list[dict[str, object]]:
    return [
        {
            "api": method.api,
            "version": method.version,
            "resource_path": method.resource_path,
            "name": method.name,
            "http_method": method.http_method,
            "path": method.path,
            "request_schema": method.request_schema,
            "response_schema": method.response_schema,
            "scopes": list(method.scopes),
        }
        for method in methods
    ]


def test_behavior_compiler_covers_gcp_control_plane_families() -> None:
    cases = {
        _method("get", "GET").identity: GcpBehaviorEffect.READ_ONE,
        _method("list", "GET").identity: GcpBehaviorEffect.READ_MANY,
        _method("create", "POST").identity: GcpBehaviorEffect.CREATE,
        _method("update", "PUT").identity: GcpBehaviorEffect.REPLACE,
        _method("patch", "PATCH").identity: GcpBehaviorEffect.PATCH,
        _method("delete", "DELETE").identity: GcpBehaviorEffect.DELETE,
        _method("getIamPolicy", "POST").identity: GcpBehaviorEffect.IAM_GET,
        _method("setIamPolicy", "POST").identity: GcpBehaviorEffect.IAM_SET,
        _method("testIamPermissions", "POST").identity: GcpBehaviorEffect.IAM_TEST,
        _method("get", "GET", resource="operations").identity: GcpBehaviorEffect.OPERATION_GET,
        _method("cancel", "POST", resource="operations").identity: GcpBehaviorEffect.OPERATION_CANCEL,
    }
    for method_id, expected in cases.items():
        method = next(
            item
            for item in (
                _method("get", "GET"),
                _method("list", "GET"),
                _method("create", "POST"),
                _method("update", "PUT"),
                _method("patch", "PATCH"),
                _method("delete", "DELETE"),
                _method("getIamPolicy", "POST"),
                _method("setIamPolicy", "POST"),
                _method("testIamPermissions", "POST"),
                _method("get", "GET", resource="operations"),
                _method("cancel", "POST", resource="operations"),
            )
            if item.identity == method_id
        )
        assert compile_behavior_rule(method).effect is expected


def test_behavior_coverage_refuses_to_call_inference_empirical_exactness() -> None:
    methods = (_method("get", "GET"), _method("create", "POST"), _method("rotate", "POST"))
    census = GcpContractCensus(
        apis=(),
        methods=methods,
        schemas=(),
        directory_digest_sha256="d" * 64,
    )
    rules, coverage = compile_behavior_corpus(census)
    assert len(rules) == 3
    assert coverage.structurally_executable_methods == 2
    assert coverage.custom_methods == (_method("rotate", "POST").identity,)
    assert coverage.structural_complete is False
    assert coverage.empirically_exact is False


@pytest.mark.asyncio
async def test_generic_crud_pagination_iam_quota_and_checkpoint_replay() -> None:
    methods = (
        _method("create", "POST"),
        _method("get", "GET"),
        _method("list", "GET"),
        _method("patch", "PATCH"),
        _method("delete", "DELETE"),
        _method("getIamPolicy", "POST"),
        _method("setIamPolicy", "POST"),
        _method("testIamPermissions", "POST"),
    )
    env = GcpExactSimulatorEnvironment(
        methods=methods,
        quota_limits={_method("create", "POST").identity: 2},
        requires_authority=False,
    )

    create = _method("create", "POST").identity
    for name in ("widgets/a", "widgets/b"):
        result = await env.actuate(
            GCP_INVOKE_CAPABILITY,
            {"method_id": create, "body": {"name": name, "value": 1}},
        )
        assert result["result"]["status_code"] == 200
        assert result["result"]["evidence"]["kind"] == "DISCOVERY_INFERRED"

    quota = await env.actuate(
        GCP_INVOKE_CAPABILITY,
        {"method_id": create, "body": {"name": "widgets/c"}},
    )
    assert quota["result"]["status_code"] == 429
    assert quota["result"]["body"]["error"]["status"] == "RESOURCE_EXHAUSTED"

    listed = await env.actuate(
        GCP_QUERY_CAPABILITY,
        {
            "method_id": _method("list", "GET").identity,
            "query": {"pageSize": 1},
        },
    )
    assert [item["name"] for item in listed["result"]["body"]["items"]] == ["widgets/a"]
    assert listed["result"]["body"]["nextPageToken"] == "offset:1"

    patched = await env.actuate(
        GCP_INVOKE_CAPABILITY,
        {
            "method_id": _method("patch", "PATCH").identity,
            "path_params": {"name": "widgets/a"},
            "query": {"updateMask": "value"},
            "body": {"value": 7, "ignored": True},
        },
    )
    assert patched["result"]["body"]["value"] == 7
    assert "ignored" not in patched["result"]["body"]

    set_policy = await env.actuate(
        GCP_INVOKE_CAPABILITY,
        {
            "method_id": _method("setIamPolicy", "POST").identity,
            "path_params": {"resource": "widgets/a"},
            "body": {
                "policy": {
                    "bindings": [
                        {
                            "role": "roles/example.reader",
                            "members": ["user:a@example.com"],
                            "permissions": ["example.widgets.get"],
                        }
                    ]
                }
            },
        },
    )
    assert set_policy["result"]["status_code"] == 200
    tested = await env.actuate(
        GCP_QUERY_CAPABILITY,
        {
            "method_id": _method("testIamPermissions", "POST").identity,
            "path_params": {"resource": "widgets/a"},
            "body": {"permissions": ["example.widgets.get", "example.widgets.delete"]},
        },
    )
    assert tested["result"]["body"] == {"permissions": ["example.widgets.get"]}

    checkpoint = await env.checkpoint()
    await env.actuate(
        GCP_INVOKE_CAPABILITY,
        {"method_id": _method("delete", "DELETE").identity, "path_params": {"name": "widgets/a"}},
    )
    assert "widgets/a" not in (await env.observe())["resources"]
    await env.restore(checkpoint)
    assert (await env.observe())["resources"]["widgets/a"]["value"] == 7


@pytest.mark.asyncio
async def test_long_running_operation_defers_mutation_until_clock_advances() -> None:
    create = _method("create", "POST", response="Operation")
    op_get = _method("get", "GET", resource="operations", response="Operation")
    env = GcpExactSimulatorEnvironment(methods=(create, op_get), requires_authority=False)

    started = await env.actuate(
        GCP_INVOKE_CAPABILITY,
        {"method_id": create.identity, "body": {"name": "widgets/lro", "value": 1}},
    )
    operation_name = started["result"]["body"]["name"]
    assert started["result"]["body"]["done"] is False
    assert "widgets/lro" not in (await env.observe())["resources"]

    await env.actuate(GCP_ADVANCE_CLOCK_CAPABILITY, {"ticks": 1})
    observed = await env.observe()
    assert observed["resources"]["widgets/lro"]["value"] == 1

    operation = await env.actuate(
        GCP_QUERY_CAPABILITY,
        {"method_id": op_get.identity, "path_params": {"name": operation_name}},
    )
    assert operation["result"]["body"]["done"] is True
    assert operation["result"]["body"]["response"]["name"] == "widgets/lro"


@pytest.mark.asyncio
async def test_exact_empirical_replay_outranks_structural_inference_and_custom_gap_refuses() -> None:
    custom = _method("rotateCredentials", "POST", response="RotateCredentialsResponse")
    request = {
        "method_id": custom.identity,
        "path_params": {"name": "projects/p/locations/global/keyRings/r/cryptoKeys/k"},
        "body": {"reason": "rotation"},
    }
    request_digest = canonical_request_digest(custom.identity, request)
    empirical_response = GcpSimulatedResponse(
        status_code=202,
        headers=(("content-type", "application/json"), ("location", "operations/real-1")),
        body={"name": "operations/real-1", "done": False},
        evidence_kind="EMPIRICAL_REPLAY",
    )
    fixture_payload = {
        "method_id": custom.identity,
        "request_digest_blake3": request_digest,
        "response": {
            "status_code": empirical_response.status_code,
            "headers": list(empirical_response.headers),
            "body": empirical_response.body,
        },
    }
    receipt = blake3(
        __import__("json").dumps(
            fixture_payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode()
    ).hexdigest()
    fixture = GcpReplayFixture(
        method_id=custom.identity,
        request_digest_blake3=request_digest,
        response=GcpSimulatedResponse(
            status_code=202,
            headers=empirical_response.headers,
            body=empirical_response.body,
            evidence_kind="EMPIRICAL_REPLAY",
            evidence_receipt=receipt,
        ),
        receipt_digest_blake3=receipt,
    )
    assert fixture.valid

    env = GcpExactSimulatorEnvironment(
        methods=(custom,), replay_fixtures=(fixture,), requires_authority=False
    )
    replayed = await env.actuate(GCP_INVOKE_CAPABILITY, request)
    assert replayed["result"]["status_code"] == 202
    assert replayed["result"]["evidence"]["kind"] == "EMPIRICAL_REPLAY"
    assert replayed["result"]["evidence"]["receipt"] == receipt

    with pytest.raises(ValueError, match="UNMODELED_GCP_METHOD"):
        await env.actuate(
            GCP_INVOKE_CAPABILITY,
            {"method_id": custom.identity, "body": {"reason": "different request"}},
        )


@pytest.mark.asyncio
async def test_factory_registers_with_real_gymact_without_static_registry_fiction() -> None:
    create = _method("create", "POST")
    get = _method("get", "GET")
    runtime = GymAct()
    runtime.register_provider(GcpExactSimulator())
    materialized = await runtime.materialize(
        MaterializationIntent(
            provider="gcp-exact-simulator",
            config={"methods": _config((create, get)), "requires_authority": False},
            idempotency_key="gcp-exact-simulator-materialize",
        )
    )
    assert materialized.accepted is True
    assert materialized.episode is not None
    episode_id = materialized.episode.episode_id
    assert {item.iri for item in runtime.capabilities(episode_id)} == {
        GCP_QUERY_CAPABILITY.iri,
        GCP_INVOKE_CAPABILITY.iri,
        GCP_ADVANCE_CLOCK_CAPABILITY.iri,
    }

    created = await runtime.act(
        ActuationIntent(
            episode_id=episode_id,
            capability=GCP_INVOKE_CAPABILITY.iri,
            payload={"method_id": create.identity, "body": {"name": "widgets/runtime"}},
            idempotency_key="gcp-create",
        )
    )
    assert created.accepted is True
    read = await runtime.read(
        episode_id,
        GCP_QUERY_CAPABILITY.iri,
        {"method_id": get.identity, "path_params": {"name": "widgets/runtime"}},
    )
    assert read["result"]["body"]["name"] == "widgets/runtime"
