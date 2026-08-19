"""Universal, evidence-bounded GCP control-plane simulator.

The simulator is contract-driven rather than service-hardcoded.  Google
Discovery methods compile to typed behavior rules; common control-plane
families execute against one deterministic semantic state machine; an exact
request can be replayed from an empirical fixture.  A structural fallback is
always labeled ``DISCOVERY_INFERRED`` and therefore can never be mistaken for
empirically exact behavior.

This is intentionally separate from real GCP actuation.  It has no Google SDK,
credential or network dependency and can run with external sockets disabled.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Any, Iterable, Mapping
from uuid import uuid4

from blake3 import blake3

from gymact.gyms.gcp_behavior import GcpBehaviorEffect, GcpBehaviorRule, compile_behavior_rule
from gymact.gyms.gcp_exact import DiscoveryMethod, GcpObservation
from gymact.models import Capability, Consequence

__all__ = [
    "GCP_ADVANCE_CLOCK_CAPABILITY",
    "GCP_EXACT_SIMULATOR_CAPABILITIES",
    "GCP_INVOKE_CAPABILITY",
    "GCP_QUERY_CAPABILITY",
    "GcpExactSimulator",
    "GcpExactSimulatorEnvironment",
    "GcpReplayFixture",
    "GcpSimulatedResponse",
    "canonical_request_digest",
]

GCP_QUERY_CAPABILITY = Capability(
    iri="urn:gymact:gcp-exact-simulator:capability:query",
    title=(
        "Execute one admitted READ-only GCP method. Payload: "
        '{"method_id": <Discovery method identity>, "path_params": {}, "query": {}, "body": {}}.'
    ),
    consequence=Consequence.READ,
    binding="gcp_query",
)
GCP_INVOKE_CAPABILITY = Capability(
    iri="urn:gymact:gcp-exact-simulator:capability:invoke",
    title=(
        "Execute one admitted consequential GCP method in the simulator. Payload: "
        '{"method_id": <Discovery method identity>, "path_params": {}, "query": {}, "body": {}}.'
    ),
    consequence=Consequence.DO,
    binding="gcp_invoke",
)
GCP_ADVANCE_CLOCK_CAPABILITY = Capability(
    iri="urn:gymact:gcp-exact-simulator:capability:advance-clock",
    title='Advance deterministic simulated time. Payload: {"ticks": <positive integer>}.',
    consequence=Consequence.DO,
    binding="gcp_advance_clock",
)
GCP_EXACT_SIMULATOR_CAPABILITIES = (
    GCP_QUERY_CAPABILITY,
    GCP_INVOKE_CAPABILITY,
    GCP_ADVANCE_CLOCK_CAPABILITY,
)


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _object(payload: Mapping[str, Any], key: str) -> dict[str, Any]:
    value = payload.get(key, {})
    if not isinstance(value, Mapping):
        raise TypeError(f"payload.{key} must be an object")
    return deepcopy(dict(value))


def _required_string(payload: Mapping[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"payload.{key} must be a non-empty string")
    return value


def canonical_request_digest(method_id: str, payload: Mapping[str, Any]) -> str:
    request = {
        "method_id": method_id,
        "path_params": _object(payload, "path_params"),
        "query": _object(payload, "query"),
        "body": _object(payload, "body"),
    }
    return blake3(_canonical_json(request).encode()).hexdigest()


@dataclass(frozen=True, slots=True)
class GcpSimulatedResponse:
    status_code: int
    headers: tuple[tuple[str, str], ...]
    body: Any
    evidence_kind: str
    evidence_receipt: str | None = None

    @property
    def canonical_body(self) -> str:
        return _canonical_json(self.body) if self.body is not None else ""

    @property
    def observation(self) -> GcpObservation:
        payload = {
            "status_code": self.status_code,
            "headers": self.headers,
            "body_kind": "empty" if self.body is None else "json",
            "canonical_body": self.canonical_body,
        }
        return GcpObservation(
            status_code=self.status_code,
            headers=self.headers,
            body_kind=payload["body_kind"],
            canonical_body=self.canonical_body,
            digest_blake3=blake3(_canonical_json(payload).encode()).hexdigest(),
        )

    def as_effect(self) -> dict[str, Any]:
        return {
            "status_code": self.status_code,
            "headers": dict(self.headers),
            "body": deepcopy(self.body),
            "evidence": {
                "kind": self.evidence_kind,
                "receipt": self.evidence_receipt,
                "response_digest_blake3": self.observation.digest_blake3,
            },
        }


@dataclass(frozen=True, slots=True)
class GcpReplayFixture:
    method_id: str
    request_digest_blake3: str
    response: GcpSimulatedResponse
    receipt_digest_blake3: str

    @property
    def payload(self) -> dict[str, Any]:
        return {
            "method_id": self.method_id,
            "request_digest_blake3": self.request_digest_blake3,
            "response": {
                "status_code": self.response.status_code,
                "headers": list(self.response.headers),
                "body": self.response.body,
            },
        }

    @property
    def valid(self) -> bool:
        expected = blake3(_canonical_json(self.payload).encode()).hexdigest()
        return bool(self.method_id and self.request_digest_blake3) and expected == self.receipt_digest_blake3

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "GcpReplayFixture":
        method_id = _required_string(value, "method_id")
        request_digest = _required_string(value, "request_digest_blake3")
        receipt = _required_string(value, "receipt_digest_blake3")
        raw_response = value.get("response")
        if not isinstance(raw_response, Mapping):
            raise TypeError("replay fixture response must be an object")
        status = raw_response.get("status_code")
        if not isinstance(status, int) or isinstance(status, bool):
            raise TypeError("replay fixture response.status_code must be an integer")
        raw_headers = raw_response.get("headers", {})
        if isinstance(raw_headers, Mapping):
            headers = tuple(sorted((str(k).lower(), str(v)) for k, v in raw_headers.items()))
        elif isinstance(raw_headers, list):
            headers = tuple(sorted((str(k).lower(), str(v)) for k, v in raw_headers))
        else:
            raise TypeError("replay fixture response.headers must be an object or pair array")
        fixture = cls(
            method_id=method_id,
            request_digest_blake3=request_digest,
            response=GcpSimulatedResponse(
                status_code=status,
                headers=headers,
                body=deepcopy(raw_response.get("body")),
                evidence_kind="EMPIRICAL_REPLAY",
                evidence_receipt=receipt,
            ),
            receipt_digest_blake3=receipt,
        )
        if not fixture.valid:
            raise ValueError(f"GCP_REPLAY_FIXTURE_DIGEST_MISMATCH:{method_id}")
        return fixture


def _google_error(status: int, status_name: str, message: str) -> GcpSimulatedResponse:
    return GcpSimulatedResponse(
        status_code=status,
        headers=(("content-type", "application/json; charset=UTF-8"),),
        body={"error": {"code": status, "message": message, "status": status_name}},
        evidence_kind="DISCOVERY_INFERRED",
    )


def _method_from_mapping(value: Mapping[str, Any]) -> DiscoveryMethod:
    required = ("api", "version", "resource_path", "name", "http_method", "path")
    missing = [key for key in required if not isinstance(value.get(key), str)]
    if missing:
        raise ValueError(f"GCP_METHOD_FIELDS_MISSING:{','.join(missing)}")
    scopes = value.get("scopes", [])
    if not isinstance(scopes, list) or not all(isinstance(item, str) for item in scopes):
        raise TypeError("method.scopes must be an array of strings")
    return DiscoveryMethod(
        api=str(value["api"]),
        version=str(value["version"]),
        resource_path=str(value["resource_path"]),
        name=str(value["name"]),
        http_method=str(value["http_method"]),
        path=str(value["path"]),
        request_schema=(str(value["request_schema"]) if value.get("request_schema") is not None else None),
        response_schema=(str(value["response_schema"]) if value.get("response_schema") is not None else None),
        scopes=tuple(sorted(scopes)),
        description=(str(value["description"]) if value.get("description") is not None else None),
    )


def _deep_merge(target: dict[str, Any], patch: Mapping[str, Any]) -> dict[str, Any]:
    result = deepcopy(target)
    for key, value in patch.items():
        if isinstance(value, Mapping) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = deepcopy(value)
    return result


def _set_path(target: dict[str, Any], path: str, source: Mapping[str, Any]) -> None:
    parts = [part for part in path.split(".") if part]
    if not parts:
        return
    src: Any = source
    for part in parts:
        if not isinstance(src, Mapping) or part not in src:
            return
        src = src[part]
    cursor = target
    for part in parts[:-1]:
        existing = cursor.get(part)
        if not isinstance(existing, dict):
            existing = {}
            cursor[part] = existing
        cursor = existing
    cursor[parts[-1]] = deepcopy(src)


class GcpExactSimulatorEnvironment:
    """One isolated GCP semantic world compiled from an admitted method graph."""

    def __init__(
        self,
        *,
        methods: Iterable[DiscoveryMethod],
        empirical_rules: Iterable[GcpBehaviorRule] = (),
        replay_fixtures: Iterable[GcpReplayFixture] = (),
        initial_resources: Mapping[str, Any] | None = None,
        quota_limits: Mapping[str, int] | None = None,
        enabled_services: Iterable[str] = (),
        enforce_service_enablement: bool = False,
        requires_authority: bool = True,
    ) -> None:
        self.environment_id = f"urn:gymact:gcp-exact-simulator:environment:{uuid4().hex}"
        self.requires_authority = requires_authority
        methods_tuple = tuple(methods)
        if not methods_tuple:
            raise ValueError("GCP_SIMULATOR_METHOD_GRAPH_EMPTY")
        self._methods = {method.identity: method for method in methods_tuple}
        if len(self._methods) != len(methods_tuple):
            raise ValueError("GCP_SIMULATOR_METHOD_GRAPH_DUPLICATED")
        empirical_by_id = {rule.method_id: rule for rule in empirical_rules}
        extras = set(empirical_by_id) - set(self._methods)
        if extras:
            raise ValueError(f"EMPIRICAL_BEHAVIOR_RULE_NOT_ADMITTED:{','.join(sorted(extras))}")
        self._rules: dict[str, GcpBehaviorRule] = {}
        for method in methods_tuple:
            rule = empirical_by_id.get(method.identity, compile_behavior_rule(method))
            if rule.source == "EMPIRICAL" and not rule.evidence_receipt:
                raise ValueError(f"EMPIRICAL_BEHAVIOR_RULE_UNRECEIPTED:{method.identity}")
            self._rules[method.identity] = rule

        fixtures = tuple(replay_fixtures)
        if any(not item.valid for item in fixtures):
            raise ValueError("GCP_REPLAY_FIXTURE_INVALID")
        self._replay: dict[tuple[str, str], GcpReplayFixture] = {}
        for fixture in fixtures:
            if fixture.method_id not in self._methods:
                raise ValueError(f"GCP_REPLAY_FIXTURE_METHOD_NOT_ADMITTED:{fixture.method_id}")
            key = (fixture.method_id, fixture.request_digest_blake3)
            if key in self._replay:
                raise ValueError(f"GCP_REPLAY_FIXTURE_DUPLICATED:{fixture.method_id}")
            self._replay[key] = fixture

        self._resources: dict[str, dict[str, Any]] = {
            str(name): deepcopy(dict(value))
            for name, value in (initial_resources or {}).items()
            if isinstance(value, Mapping)
        }
        self._iam: dict[str, dict[str, Any]] = {}
        self._operations: dict[str, dict[str, Any]] = {}
        self._quota_limits: dict[str, int] = {}
        for key, limit in (quota_limits or {}).items():
            if not isinstance(limit, int) or isinstance(limit, bool) or limit < 0:
                raise ValueError(f"quota limit must be a non-negative integer: {key}")
            self._quota_limits[str(key)] = limit
        self._quota_usage: dict[str, int] = {}
        self._enabled_services = set(enabled_services)
        self._enforce_service_enablement = enforce_service_enablement
        self._clock = 0
        self._sequence = 0
        self._audit: list[dict[str, Any]] = []
        self._closed = False

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError("environment is torn down")

    def capabilities(self) -> tuple[Capability, ...]:
        self._ensure_open()
        return GCP_EXACT_SIMULATOR_CAPABILITIES

    async def observe(self) -> dict[str, Any]:
        self._ensure_open()
        return self._snapshot()

    async def actuate(self, capability: Capability, payload: dict[str, Any]) -> dict[str, Any]:
        self._ensure_open()
        if capability.binding == GCP_ADVANCE_CLOCK_CAPABILITY.binding:
            ticks = payload.get("ticks", 1)
            if not isinstance(ticks, int) or isinstance(ticks, bool) or ticks <= 0:
                raise ValueError("payload.ticks must be a positive integer")
            before = self._snapshot()
            self._clock += ticks
            self._complete_due_operations()
            return {
                "before": before,
                "after": self._snapshot(),
                "capability": capability.iri,
                "result": {"logical_clock": self._clock},
            }
        if capability.binding not in {GCP_QUERY_CAPABILITY.binding, GCP_INVOKE_CAPABILITY.binding}:
            raise ValueError(f"unsupported provider binding: {capability.binding}")

        method_id = _required_string(payload, "method_id")
        method = self._methods.get(method_id)
        if method is None:
            raise ValueError(f"GCP_METHOD_NOT_ADMITTED:{method_id}")
        rule = self._rules[method_id]
        if capability.binding == GCP_QUERY_CAPABILITY.binding and not rule.read_only:
            raise ValueError(f"GCP_DO_METHOD_REQUIRES_INVOKE_CAPABILITY:{method_id}")
        if capability.binding == GCP_INVOKE_CAPABILITY.binding and rule.read_only:
            raise ValueError(f"GCP_READ_METHOD_REQUIRES_QUERY_CAPABILITY:{method_id}")

        before = self._snapshot()
        response = self._execute(method, rule, payload)
        self._record_audit(method_id, payload, response)
        return {
            "before": before,
            "after": self._snapshot(),
            "capability": capability.iri,
            "method_id": method_id,
            "result": response.as_effect(),
        }

    async def verify(self, expected: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
        self._ensure_open()
        observed = self._snapshot()
        passed = all(observed.get(key) == value for key, value in expected.items())
        return passed, observed

    async def checkpoint(self) -> dict[str, Any]:
        self._ensure_open()
        return self._snapshot()

    async def restore(self, checkpoint: dict[str, Any]) -> None:
        self._ensure_open()
        required = {
            "logical_clock",
            "sequence",
            "resources",
            "iam_policies",
            "operations",
            "quota_usage",
            "enabled_services",
            "audit_log",
        }
        if not required.issubset(checkpoint):
            raise ValueError("checkpoint is not a GCP exact simulator checkpoint")
        self._clock = int(checkpoint["logical_clock"])
        self._sequence = int(checkpoint["sequence"])
        self._resources = deepcopy(checkpoint["resources"])
        self._iam = deepcopy(checkpoint["iam_policies"])
        self._operations = deepcopy(checkpoint["operations"])
        self._quota_usage = deepcopy(checkpoint["quota_usage"])
        self._enabled_services = set(checkpoint["enabled_services"])
        self._audit = deepcopy(checkpoint["audit_log"])

    async def teardown(self) -> None:
        self._closed = True

    def _snapshot(self) -> dict[str, Any]:
        return {
            "logical_clock": self._clock,
            "sequence": self._sequence,
            "contract_method_count": len(self._methods),
            "structurally_executable_method_count": sum(
                rule.structurally_executable for rule in self._rules.values()
            ),
            "empirically_admitted_behavior_count": sum(
                rule.empirically_admitted for rule in self._rules.values()
            ),
            "empirical_replay_fixture_count": len(self._replay),
            "resources": deepcopy(self._resources),
            "iam_policies": deepcopy(self._iam),
            "operations": deepcopy(self._operations),
            "quota_usage": dict(self._quota_usage),
            "enabled_services": sorted(self._enabled_services),
            "audit_log": deepcopy(self._audit),
        }

    def _execute(
        self,
        method: DiscoveryMethod,
        rule: GcpBehaviorRule,
        payload: Mapping[str, Any],
        *,
        allow_lro_completion: bool = False,
    ) -> GcpSimulatedResponse:
        request_digest = canonical_request_digest(method.identity, payload)
        fixture = self._replay.get((method.identity, request_digest))
        if fixture is not None:
            return fixture.response

        if rule.effect is GcpBehaviorEffect.CUSTOM and not rule.empirically_admitted:
            raise ValueError(f"UNMODELED_GCP_METHOD:{method.identity}")
        if self._enforce_service_enablement and method.api not in self._enabled_services:
            return _google_error(403, "PERMISSION_DENIED", f"API not enabled: {method.api}")
        quota_error = self._consume_quota(method.identity, mutation=not rule.read_only)
        if quota_error is not None:
            return quota_error

        if rule.long_running and not allow_lro_completion:
            return self._start_operation(method, rule, payload)
        return self._execute_effect(method, rule, payload)

    def _execute_effect(
        self,
        method: DiscoveryMethod,
        rule: GcpBehaviorRule,
        payload: Mapping[str, Any],
    ) -> GcpSimulatedResponse:
        effect = rule.effect
        if effect is GcpBehaviorEffect.READ_ONE:
            return self._read_one(payload)
        if effect is GcpBehaviorEffect.READ_MANY:
            return self._read_many(method, payload)
        if effect is GcpBehaviorEffect.CREATE:
            return self._create(method, payload)
        if effect is GcpBehaviorEffect.REPLACE:
            return self._replace(payload)
        if effect is GcpBehaviorEffect.PATCH:
            return self._patch(payload)
        if effect is GcpBehaviorEffect.DELETE:
            return self._delete(payload)
        if effect is GcpBehaviorEffect.IAM_GET:
            return self._iam_get(payload)
        if effect is GcpBehaviorEffect.IAM_SET:
            return self._iam_set(payload)
        if effect is GcpBehaviorEffect.IAM_TEST:
            return self._iam_test(payload)
        if effect is GcpBehaviorEffect.SERVICE_ENABLE:
            return self._service_enable(payload)
        if effect is GcpBehaviorEffect.SERVICE_DISABLE:
            return self._service_disable(payload)
        if effect is GcpBehaviorEffect.OPERATION_GET:
            return self._operation_get(payload)
        if effect is GcpBehaviorEffect.OPERATION_LIST:
            return self._operation_list(payload)
        if effect is GcpBehaviorEffect.OPERATION_CANCEL:
            return self._operation_cancel(payload)
        if effect is GcpBehaviorEffect.OPERATION_DELETE:
            return self._operation_delete(payload)
        if effect is GcpBehaviorEffect.OPERATION_WAIT:
            return self._operation_wait(payload)

        # An empirically admitted CUSTOM behavior rule establishes that this
        # method belongs in the executable graph, but without an exact replay
        # fixture there is no lawful generalized transition to invent.
        raise ValueError(f"EMPIRICAL_CUSTOM_METHOD_REQUIRES_REPLAY_FIXTURE:{method.identity}")

    def _resource_name(self, payload: Mapping[str, Any], *, create: bool = False) -> str | None:
        path_params = _object(payload, "path_params")
        body = _object(payload, "body")
        for key in ("name", "resource", "resourceName"):
            value = path_params.get(key)
            if isinstance(value, str) and value:
                return value
        body_name = body.get("name")
        if isinstance(body_name, str) and body_name:
            parent = path_params.get("parent")
            if create and isinstance(parent, str) and parent and not body_name.startswith(parent):
                return f"{parent.rstrip('/')}/{body_name.lstrip('/')}"
            return body_name
        if create:
            parent = path_params.get("parent")
            query = _object(payload, "query")
            identifier = next(
                (
                    value
                    for key, value in sorted(query.items())
                    if key.lower().endswith("id") and isinstance(value, str) and value
                ),
                None,
            )
            if isinstance(parent, str) and parent and identifier:
                return f"{parent.rstrip('/')}/{identifier}"
        return None

    def _read_one(self, payload: Mapping[str, Any]) -> GcpSimulatedResponse:
        name = self._resource_name(payload)
        if not name or name not in self._resources:
            return _google_error(404, "NOT_FOUND", f"Resource not found: {name or '<unspecified>'}")
        return self._ok(self._resources[name])

    def _read_many(self, method: DiscoveryMethod, payload: Mapping[str, Any]) -> GcpSimulatedResponse:
        path_params = _object(payload, "path_params")
        query = _object(payload, "query")
        parent = path_params.get("parent")
        candidates = [
            deepcopy(value)
            for name, value in sorted(self._resources.items())
            if not isinstance(parent, str) or name.startswith(parent.rstrip("/") + "/")
        ]
        page_size = query.get("pageSize", query.get("page_size", 100))
        if not isinstance(page_size, int) or isinstance(page_size, bool) or page_size < 0:
            return _google_error(400, "INVALID_ARGUMENT", "pageSize must be a non-negative integer")
        page_size = min(page_size or 100, 1000)
        raw_token = query.get("pageToken", query.get("page_token", ""))
        if raw_token in (None, ""):
            offset = 0
        elif isinstance(raw_token, str) and raw_token.startswith("offset:"):
            try:
                offset = int(raw_token.split(":", 1)[1])
            except ValueError:
                return _google_error(400, "INVALID_ARGUMENT", "invalid pageToken")
        else:
            return _google_error(400, "INVALID_ARGUMENT", "invalid pageToken")
        page = candidates[offset : offset + page_size]
        next_offset = offset + len(page)
        body: dict[str, Any] = {"items": page}
        if next_offset < len(candidates):
            body["nextPageToken"] = f"offset:{next_offset}"
        body["_gymact_response_schema"] = method.response_schema
        return self._ok(body)

    def _create(self, method: DiscoveryMethod, payload: Mapping[str, Any]) -> GcpSimulatedResponse:
        body = _object(payload, "body")
        name = self._resource_name(payload, create=True)
        if not name:
            self._sequence += 1
            name = f"projects/gymact-simulated/resources/{method.api}-{self._sequence:08d}"
        if name in self._resources:
            return _google_error(409, "ALREADY_EXISTS", f"Resource already exists: {name}")
        resource = deepcopy(body)
        resource["name"] = name
        resource.setdefault("_gymact_api", method.api)
        resource.setdefault("_gymact_created_at", self._clock)
        self._resources[name] = resource
        return self._ok(resource)

    def _replace(self, payload: Mapping[str, Any]) -> GcpSimulatedResponse:
        name = self._resource_name(payload)
        if not name or name not in self._resources:
            return _google_error(404, "NOT_FOUND", f"Resource not found: {name or '<unspecified>'}")
        body = _object(payload, "body")
        body["name"] = name
        self._resources[name] = deepcopy(body)
        return self._ok(body)

    def _patch(self, payload: Mapping[str, Any]) -> GcpSimulatedResponse:
        name = self._resource_name(payload)
        if not name or name not in self._resources:
            return _google_error(404, "NOT_FOUND", f"Resource not found: {name or '<unspecified>'}")
        body = _object(payload, "body")
        query = _object(payload, "query")
        raw_mask = query.get("updateMask", query.get("update_mask"))
        if isinstance(raw_mask, str) and raw_mask.strip():
            updated = deepcopy(self._resources[name])
            for path in (item.strip() for item in raw_mask.split(",")):
                _set_path(updated, path, body)
        else:
            updated = _deep_merge(self._resources[name], body)
        updated["name"] = name
        self._resources[name] = updated
        return self._ok(updated)

    def _delete(self, payload: Mapping[str, Any]) -> GcpSimulatedResponse:
        name = self._resource_name(payload)
        if not name or name not in self._resources:
            return _google_error(404, "NOT_FOUND", f"Resource not found: {name or '<unspecified>'}")
        del self._resources[name]
        self._iam.pop(name, None)
        return self._ok({})

    def _iam_target(self, payload: Mapping[str, Any]) -> str | None:
        path_params = _object(payload, "path_params")
        for key in ("resource", "name"):
            value = path_params.get(key)
            if isinstance(value, str) and value:
                return value
        return None

    def _iam_get(self, payload: Mapping[str, Any]) -> GcpSimulatedResponse:
        target = self._iam_target(payload)
        if not target:
            return _google_error(400, "INVALID_ARGUMENT", "resource is required")
        return self._ok(self._iam.get(target, {"bindings": [], "etag": ""}))

    def _iam_set(self, payload: Mapping[str, Any]) -> GcpSimulatedResponse:
        target = self._iam_target(payload)
        if not target:
            return _google_error(400, "INVALID_ARGUMENT", "resource is required")
        body = _object(payload, "body")
        policy = body.get("policy", body)
        if not isinstance(policy, Mapping):
            return _google_error(400, "INVALID_ARGUMENT", "policy must be an object")
        normalized = deepcopy(dict(policy))
        normalized.setdefault("bindings", [])
        normalized["etag"] = sha256(_canonical_json(normalized.get("bindings", [])).encode()).hexdigest()[:24]
        self._iam[target] = normalized
        return self._ok(normalized)

    def _iam_test(self, payload: Mapping[str, Any]) -> GcpSimulatedResponse:
        target = self._iam_target(payload)
        if not target:
            return _google_error(400, "INVALID_ARGUMENT", "resource is required")
        body = _object(payload, "body")
        requested = body.get("permissions", [])
        if not isinstance(requested, list) or not all(isinstance(item, str) for item in requested):
            return _google_error(400, "INVALID_ARGUMENT", "permissions must be an array of strings")
        # A policy binding's optional ``permissions`` extension is deliberately
        # explicit simulation data; role-to-permission expansion is not guessed.
        allowed: set[str] = set()
        for binding in self._iam.get(target, {}).get("bindings", []):
            if isinstance(binding, Mapping):
                permissions = binding.get("permissions", [])
                if isinstance(permissions, list):
                    allowed.update(str(item) for item in permissions)
        return self._ok({"permissions": [item for item in requested if item in allowed]})

    def _service_names(self, payload: Mapping[str, Any]) -> list[str]:
        path_params = _object(payload, "path_params")
        body = _object(payload, "body")
        result: list[str] = []
        name = path_params.get("name")
        if isinstance(name, str) and name:
            result.append(name.rsplit("/services/", 1)[-1])
        raw = body.get("serviceIds", body.get("services", []))
        if isinstance(raw, list):
            result.extend(str(item) for item in raw if isinstance(item, str) and item)
        return sorted(set(result))

    def _service_enable(self, payload: Mapping[str, Any]) -> GcpSimulatedResponse:
        services = self._service_names(payload)
        if not services:
            return _google_error(400, "INVALID_ARGUMENT", "service name is required")
        self._enabled_services.update(services)
        return self._ok({"services": services})

    def _service_disable(self, payload: Mapping[str, Any]) -> GcpSimulatedResponse:
        services = self._service_names(payload)
        if not services:
            return _google_error(400, "INVALID_ARGUMENT", "service name is required")
        for service in services:
            self._enabled_services.discard(service)
        return self._ok({"services": services})

    def _operation_name(self, payload: Mapping[str, Any]) -> str | None:
        path_params = _object(payload, "path_params")
        name = path_params.get("name")
        return name if isinstance(name, str) and name else None

    def _operation_get(self, payload: Mapping[str, Any]) -> GcpSimulatedResponse:
        name = self._operation_name(payload)
        operation = self._operations.get(name or "")
        if operation is None:
            return _google_error(404, "NOT_FOUND", f"Operation not found: {name or '<unspecified>'}")
        return self._ok(operation)

    def _operation_list(self, payload: Mapping[str, Any]) -> GcpSimulatedResponse:
        path_params = _object(payload, "path_params")
        parent = path_params.get("name", path_params.get("parent"))
        operations = [
            deepcopy(value)
            for name, value in sorted(self._operations.items())
            if not isinstance(parent, str) or name.startswith(parent.rstrip("/") + "/")
        ]
        return self._ok({"operations": operations})

    def _operation_cancel(self, payload: Mapping[str, Any]) -> GcpSimulatedResponse:
        name = self._operation_name(payload)
        operation = self._operations.get(name or "")
        if operation is None:
            return _google_error(404, "NOT_FOUND", f"Operation not found: {name or '<unspecified>'}")
        if not operation.get("done"):
            operation["done"] = True
            operation["error"] = {"code": 1, "message": "Operation cancelled", "status": "CANCELLED"}
            operation.pop("_pending", None)
        return self._ok({})

    def _operation_delete(self, payload: Mapping[str, Any]) -> GcpSimulatedResponse:
        name = self._operation_name(payload)
        if not name or name not in self._operations:
            return _google_error(404, "NOT_FOUND", f"Operation not found: {name or '<unspecified>'}")
        del self._operations[name]
        return self._ok({})

    def _operation_wait(self, payload: Mapping[str, Any]) -> GcpSimulatedResponse:
        name = self._operation_name(payload)
        operation = self._operations.get(name or "")
        if operation is None:
            return _google_error(404, "NOT_FOUND", f"Operation not found: {name or '<unspecified>'}")
        return self._ok(operation)

    def _start_operation(
        self,
        method: DiscoveryMethod,
        rule: GcpBehaviorRule,
        payload: Mapping[str, Any],
    ) -> GcpSimulatedResponse:
        self._sequence += 1
        operation_name = f"operations/gymact-{self._sequence:08d}"
        operation = {
            "name": operation_name,
            "done": False,
            "metadata": {
                "method": method.identity,
                "submittedAtLogicalClock": self._clock,
            },
            "_complete_at": self._clock + 1,
            "_pending": {
                "method_id": method.identity,
                "payload": {
                    "path_params": _object(payload, "path_params"),
                    "query": _object(payload, "query"),
                    "body": _object(payload, "body"),
                },
                "effect": rule.effect.value,
            },
        }
        self._operations[operation_name] = operation
        public = {key: deepcopy(value) for key, value in operation.items() if not key.startswith("_")}
        return self._ok(public)

    def _complete_due_operations(self) -> None:
        for operation in self._operations.values():
            if operation.get("done") or operation.get("_complete_at", self._clock + 1) > self._clock:
                continue
            pending = operation.get("_pending")
            if not isinstance(pending, Mapping):
                continue
            method_id = str(pending["method_id"])
            method = self._methods[method_id]
            rule = self._rules[method_id]
            response = self._execute(method, rule, pending["payload"], allow_lro_completion=True)
            operation["done"] = True
            if response.status_code >= 400:
                operation["error"] = deepcopy(response.body.get("error", response.body))
            else:
                operation["response"] = deepcopy(response.body)
            operation.pop("_pending", None)
            operation.pop("_complete_at", None)

    def _consume_quota(self, method_id: str, *, mutation: bool) -> GcpSimulatedResponse | None:
        if not mutation:
            return None
        limit = self._quota_limits.get(method_id)
        if limit is None:
            return None
        used = self._quota_usage.get(method_id, 0)
        if used >= limit:
            return _google_error(429, "RESOURCE_EXHAUSTED", f"Quota exceeded for {method_id}")
        self._quota_usage[method_id] = used + 1
        return None

    def _record_audit(
        self,
        method_id: str,
        payload: Mapping[str, Any],
        response: GcpSimulatedResponse,
    ) -> None:
        self._sequence += 1
        self._audit.append(
            {
                "sequence": self._sequence,
                "logical_clock": self._clock,
                "method_id": method_id,
                "request_digest_blake3": canonical_request_digest(method_id, payload),
                "response_digest_blake3": response.observation.digest_blake3,
                "status_code": response.status_code,
                "evidence_kind": response.evidence_kind,
                "evidence_receipt": response.evidence_receipt,
            }
        )

    @staticmethod
    def _ok(body: Any) -> GcpSimulatedResponse:
        return GcpSimulatedResponse(
            status_code=200,
            headers=(("content-type", "application/json; charset=UTF-8"),),
            body=deepcopy(body),
            evidence_kind="DISCOVERY_INFERRED",
        )


class GcpExactSimulator:
    """EnvironmentProvider-compatible factory for a contract-driven GCP world.

    The class intentionally does not call itself a built-in ``*Provider``:
    its capability graph is configuration-dependent and therefore cannot be
    truthfully flattened into GymAct's static generated provider registry.
    Consumers register an instance directly with ``GymAct.register_provider``.
    """

    name = "gcp-exact-simulator"
    materialization_requires_authority = False

    async def materialize(
        self,
        *,
        scenario: str | None,
        config: dict[str, Any],
    ) -> GcpExactSimulatorEnvironment:
        del scenario
        raw_methods = config.get("methods")
        if not isinstance(raw_methods, list) or not raw_methods:
            raise ValueError("config.methods must be a non-empty array of Discovery method objects")
        methods = tuple(
            _method_from_mapping(value)
            for value in raw_methods
            if isinstance(value, Mapping)
        )
        if len(methods) != len(raw_methods):
            raise TypeError("config.methods entries must be objects")

        empirical_rules: list[GcpBehaviorRule] = []
        for value in config.get("empirical_rules", []):
            if not isinstance(value, Mapping):
                raise TypeError("config.empirical_rules entries must be objects")
            method_id = _required_string(value, "method_id")
            method = next((item for item in methods if item.identity == method_id), None)
            if method is None:
                raise ValueError(f"EMPIRICAL_BEHAVIOR_RULE_NOT_ADMITTED:{method_id}")
            receipt = _required_string(value, "evidence_receipt")
            raw_effect = value.get("effect")
            base = compile_behavior_rule(method)
            if raw_effect is None:
                effect = base.effect
            else:
                effect = GcpBehaviorEffect(str(raw_effect))
            empirical_rules.append(
                GcpBehaviorRule(
                    method_id=method_id,
                    effect=effect,
                    http_method=method.http_method.upper(),
                    path=method.path,
                    response_schema=method.response_schema,
                    source="EMPIRICAL",
                    evidence_receipt=receipt,
                )
            )

        replay_fixtures = tuple(
            GcpReplayFixture.from_mapping(value)
            for value in config.get("replay_fixtures", [])
            if isinstance(value, Mapping)
        )
        if len(replay_fixtures) != len(config.get("replay_fixtures", [])):
            raise TypeError("config.replay_fixtures entries must be objects")

        initial_resources = config.get("initial_resources", {})
        quota_limits = config.get("quota_limits", {})
        enabled_services = config.get("enabled_services", [])
        if not isinstance(initial_resources, Mapping):
            raise TypeError("config.initial_resources must be an object")
        if not isinstance(quota_limits, Mapping):
            raise TypeError("config.quota_limits must be an object")
        if not isinstance(enabled_services, list) or not all(
            isinstance(item, str) for item in enabled_services
        ):
            raise TypeError("config.enabled_services must be an array of strings")
        enforce = config.get("enforce_service_enablement", False)
        requires_authority = config.get("requires_authority", True)
        if not isinstance(enforce, bool):
            raise TypeError("config.enforce_service_enablement must be a boolean")
        if not isinstance(requires_authority, bool):
            raise TypeError("config.requires_authority must be a boolean")

        return GcpExactSimulatorEnvironment(
            methods=methods,
            empirical_rules=empirical_rules,
            replay_fixtures=replay_fixtures,
            initial_resources=initial_resources,
            quota_limits={str(key): int(value) for key, value in quota_limits.items()},
            enabled_services=enabled_services,
            enforce_service_enablement=enforce,
            requires_authority=requires_authority,
        )
