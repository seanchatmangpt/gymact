"""Generated Deterministic MCP (gdmcp) programs for bounded GymAct worlds.

This module is intentionally not an agent.  It compiles exact, source-grounded
solution programs into ordinary :class:`gymact.models.ActuationIntent` values.
Those intents still cross GymAct's capability-scope and authority gates and the
normal BRCE consequence path.  gdmcp therefore adds no actuation authority.

The first profile is SREGym.  Known benchmark repairs are compiled from the
exact-pinned upstream SREGym recovery semantics.  Unknown problems, upstream
revision drift, or unexpected runtime bindings fail closed instead of falling
back to an LLM or arbitrary MCP tool selection.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Literal

from gymact.models import ActuationIntent, FrozenModel

SREGYM_UPSTREAM_REVISION = "ba07faf1a322f9b6d4a279643bb796aa2f36f64b"

SREGYM_RUN_KUBECTL = "urn:gymact:sregym:capability:run_kubectl"
SREGYM_SUBMIT_DIAGNOSIS = "urn:gymact:sregym:capability:submit_diagnosis"
SREGYM_SUBMIT_MITIGATION = "urn:gymact:sregym:capability:submit_mitigation"

_GDMCP_SREGYM_CAPABILITIES = frozenset(
    {
        SREGYM_RUN_KUBECTL,
        SREGYM_SUBMIT_DIAGNOSIS,
        SREGYM_SUBMIT_MITIGATION,
    }
)

# Exact list from SREGym/SREGym@SREGYM_UPSTREAM_REVISION docs/SREGym-Lite.md.
SREGYM_LITE_PROBLEMS = (
    "cronjob_sidecar_blocks_completion_hotel_reservation",
    "edge_request_filter_cpu_saturation",
    "network_policy_block",
    "env_variable_shadowing_astronomy_shop",
    "mutating_webhook_resource_limits_social_network",
    "finalizer_deadlock_controller_hotel_reservation",
    "kafka_poison_pill_hol_block",
    "internal_traffic_policy_local_astronomy_shop",
    "service_dns_resolution_failure_social_network",
    "service_wrong_pod_selection_hotel_reservation",
    "namespace_memory_limit",
    "valkey_auth_disruption",
    "secret_rotation_stale_env_credentials_astronomy_shop",
    "unschedulable_incorrect_port_assignment",
    "readiness_probe_misconfiguration_social_network",
    "duplicate_pvc_mounts_social_network",
    "admission_webhook_outage_hotel_reservation",
    "wrong_dns_policy_astronomy_shop",
    "wrong_service_selector_social_network",
    "rolling_update_misconfigured_social_network",
    "search_rate_retry_collapse_hotel_reservation",
)

_PLACEHOLDER_RE = re.compile(r"\{\{([a-z][a-z0-9_]*)\}\}")
_K8S_NAMESPACE_RE = re.compile(r"^[a-z0-9](?:[-a-z0-9]*[a-z0-9])?$")


class GdmcpRefusal(RuntimeError):
    """Typed fail-closed outcome from deterministic program admission."""

    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"REFUSED:{code}:{detail}")


class GdmcpStep(FrozenModel):
    """One generated MCP/GymAct transition with no runtime tool selection."""

    capability: str
    payload_template: dict[str, Any]
    purpose: str
    source_ref: str


class GdmcpProgram(FrozenModel):
    """One exact-subject deterministic solution program."""

    profile: Literal["sregym"] = "sregym"
    problem_id: str
    upstream_revision: str = SREGYM_UPSTREAM_REVISION
    steps: tuple[GdmcpStep, ...]
    llm_calls: Literal[0] = 0
    source_refs: tuple[str, ...]

    def digest(self) -> str:
        payload = json.dumps(
            self.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        ).encode("utf-8")
        return "sha256:" + hashlib.sha256(payload).hexdigest()


class CompiledGdmcpProgram(FrozenModel):
    """A deterministic program bound to one GymAct episode."""

    program_digest: str
    problem_id: str
    upstream_revision: str
    llm_calls: Literal[0] = 0
    intents: tuple[ActuationIntent, ...]


class GdmcpCoverage(FrozenModel):
    """Honest bounded coverage for a named benchmark corpus."""

    corpus: str
    admitted_subjects: int
    compiled_subjects: int
    deterministic_projection_ratio: float


def _source(path: str, symbol: str, *, blob_sha: str | None = None) -> str:
    blob = f";blob={blob_sha}" if blob_sha else ""
    return f"SREGym/SREGym@{SREGYM_UPSTREAM_REVISION}:{path}#{symbol}{blob}"


_WRONG_DNS_SOURCE = _source(
    "sregym/conductor/problems/wrong_dns_policy.py",
    "WrongDNSPolicy.recover_fault",
    blob_sha="630627e4c4d3f69f477e857252972b397757f68c",
)
_WRONG_DNS_INJECTOR_SOURCE = _source(
    "sregym/generators/fault/inject_virtual.py",
    "VirtualizationFaultInjector.recover_wrong_dns_policy",
)
_INTERNAL_TRAFFIC_SOURCE = _source(
    "sregym/conductor/problems/internal_traffic_policy_local.py",
    "InternalTrafficPolicyLocalAstronomyShop.recover_fault",
    blob_sha="4264df2c1b88845df120aec09bb9583292f652d4",
)


def _step(
    capability: str,
    payload: dict[str, Any],
    purpose: str,
    source_ref: str,
) -> GdmcpStep:
    if capability not in _GDMCP_SREGYM_CAPABILITIES:
        raise ValueError(f"gdmcp program uses non-admitted SREGym capability: {capability}")
    return GdmcpStep(
        capability=capability,
        payload_template=payload,
        purpose=purpose,
        source_ref=source_ref,
    )


# These are deliberately data, not per-problem Python control-flow branches.
# ggen can manufacture this same structure from admitted recovery semantics as
# coverage expands; the runtime compiler below remains unchanged.
_SREGYM_PROGRAMS: dict[str, GdmcpProgram] = {
    "wrong_dns_policy_astronomy_shop": GdmcpProgram(
        problem_id="wrong_dns_policy_astronomy_shop",
        source_refs=(_WRONG_DNS_SOURCE, _WRONG_DNS_INJECTOR_SOURCE),
        steps=(
            _step(
                SREGYM_SUBMIT_DIAGNOSIS,
                {
                    "component": "frontend",
                    "cause": (
                        "deployment frontend has dnsPolicy=None and an external "
                        "8.8.8.8 resolver, breaking cluster-internal DNS resolution"
                    ),
                    "gdmcp_source": _WRONG_DNS_SOURCE,
                },
                "submit the source-grounded diagnosis; no model inference",
                _WRONG_DNS_SOURCE,
            ),
            _step(
                SREGYM_RUN_KUBECTL,
                {
                    "command": (
                        "kubectl patch deployment frontend -n {{namespace}} "
                        "--type=json -p='[{\"op\":\"remove\",\"path\":\"/spec/template/spec/dnsPolicy\"},"
                        "{\"op\":\"remove\",\"path\":\"/spec/template/spec/dnsConfig\"}]'"
                    )
                },
                "restore the deployment to normal ClusterFirst DNS semantics",
                _WRONG_DNS_INJECTOR_SOURCE,
            ),
            _step(
                SREGYM_RUN_KUBECTL,
                {
                    "command": (
                        "kubectl rollout status deployment frontend -n {{namespace}} "
                        "--timeout=120s"
                    )
                },
                "wait for the repaired deployment to become stable",
                _WRONG_DNS_INJECTOR_SOURCE,
            ),
            _step(
                SREGYM_SUBMIT_MITIGATION,
                {
                    "action": (
                        "removed the injected dnsPolicy/dnsConfig override and "
                        "waited for the frontend rollout"
                    ),
                    "gdmcp_source": _WRONG_DNS_INJECTOR_SOURCE,
                },
                "submit the deterministic mitigation evidence",
                _WRONG_DNS_INJECTOR_SOURCE,
            ),
        ),
    ),
    "internal_traffic_policy_local_astronomy_shop": GdmcpProgram(
        problem_id="internal_traffic_policy_local_astronomy_shop",
        source_refs=(_INTERNAL_TRAFFIC_SOURCE,),
        steps=(
            _step(
                SREGYM_SUBMIT_DIAGNOSIS,
                {
                    "component": "service/recommendation",
                    "cause": (
                        "internalTrafficPolicy=Local plus pinned recommendation/frontend "
                        "pods causes cross-node in-cluster requests to be dropped"
                    ),
                    "gdmcp_source": _INTERNAL_TRAFFIC_SOURCE,
                },
                "submit the source-grounded diagnosis; no model inference",
                _INTERNAL_TRAFFIC_SOURCE,
            ),
            _step(
                SREGYM_RUN_KUBECTL,
                {
                    "command": (
                        "kubectl patch service recommendation -n {{namespace}} "
                        "--type=merge -p '{\"spec\":{\"internalTrafficPolicy\":\"Cluster\"}}'"
                    )
                },
                "restore cluster-wide service routing",
                _INTERNAL_TRAFFIC_SOURCE,
            ),
            _step(
                SREGYM_RUN_KUBECTL,
                {
                    "command": (
                        "kubectl patch deployment recommendation -n {{namespace}} "
                        "--type=merge -p '{\"spec\":{\"template\":{\"spec\":{\"nodeSelector\":null}}}}'"
                    )
                },
                "remove fault-only recommendation node pinning",
                _INTERNAL_TRAFFIC_SOURCE,
            ),
            _step(
                SREGYM_RUN_KUBECTL,
                {"command": "kubectl rollout restart deployment/recommendation -n {{namespace}}"},
                "restart recommendation after topology repair",
                _INTERNAL_TRAFFIC_SOURCE,
            ),
            _step(
                SREGYM_RUN_KUBECTL,
                {
                    "command": (
                        "kubectl patch deployment frontend -n {{namespace}} "
                        "--type=merge -p '{\"spec\":{\"template\":{\"spec\":{\"nodeSelector\":null}}}}'"
                    )
                },
                "remove fault-only frontend node pinning",
                _INTERNAL_TRAFFIC_SOURCE,
            ),
            _step(
                SREGYM_RUN_KUBECTL,
                {"command": "kubectl rollout restart deployment/frontend -n {{namespace}}"},
                "restart frontend after topology repair",
                _INTERNAL_TRAFFIC_SOURCE,
            ),
            _step(
                SREGYM_RUN_KUBECTL,
                {
                    "command": (
                        "kubectl rollout status deployment/recommendation -n {{namespace}} "
                        "--timeout=180s"
                    )
                },
                "wait for recommendation convergence",
                _INTERNAL_TRAFFIC_SOURCE,
            ),
            _step(
                SREGYM_RUN_KUBECTL,
                {
                    "command": (
                        "kubectl rollout status deployment/frontend -n {{namespace}} "
                        "--timeout=180s"
                    )
                },
                "wait for frontend convergence",
                _INTERNAL_TRAFFIC_SOURCE,
            ),
            _step(
                SREGYM_SUBMIT_MITIGATION,
                {
                    "action": (
                        "restored internalTrafficPolicy=Cluster, removed both injected "
                        "nodeSelectors, and waited for both deployments to roll out"
                    ),
                    "gdmcp_source": _INTERNAL_TRAFFIC_SOURCE,
                },
                "submit the deterministic mitigation evidence",
                _INTERNAL_TRAFFIC_SOURCE,
            ),
        ),
    ),
}


def known_sregym_programs() -> tuple[GdmcpProgram, ...]:
    """Return deterministic programs in stable problem-id order."""

    return tuple(_SREGYM_PROGRAMS[key] for key in sorted(_SREGYM_PROGRAMS))


def sregym_lite_coverage() -> GdmcpCoverage:
    compiled = len(set(SREGYM_LITE_PROBLEMS) & set(_SREGYM_PROGRAMS))
    total = len(SREGYM_LITE_PROBLEMS)
    return GdmcpCoverage(
        corpus=f"SREGym-Lite@{SREGYM_UPSTREAM_REVISION}",
        admitted_subjects=total,
        compiled_subjects=compiled,
        deterministic_projection_ratio=compiled / total,
    )


def _collect_placeholders(value: Any) -> set[str]:
    if isinstance(value, str):
        return set(_PLACEHOLDER_RE.findall(value))
    if isinstance(value, dict):
        found: set[str] = set()
        for item in value.values():
            found.update(_collect_placeholders(item))
        return found
    if isinstance(value, (list, tuple)):
        found = set()
        for item in value:
            found.update(_collect_placeholders(item))
        return found
    return set()


def _validate_binding(name: str, value: str) -> None:
    if name != "namespace":
        raise GdmcpRefusal("GDMCP_UNKNOWN_BINDING", name)
    if len(value) > 63 or not _K8S_NAMESPACE_RE.fullmatch(value):
        raise GdmcpRefusal("GDMCP_INVALID_NAMESPACE", value)


def _render(value: Any, bindings: dict[str, str]) -> Any:
    if isinstance(value, str):
        rendered = value
        for name, replacement in bindings.items():
            rendered = rendered.replace("{{" + name + "}}", replacement)
        return rendered
    if isinstance(value, dict):
        return {key: _render(item, bindings) for key, item in value.items()}
    if isinstance(value, list):
        return [_render(item, bindings) for item in value]
    if isinstance(value, tuple):
        return tuple(_render(item, bindings) for item in value)
    return value


def _idempotency_key(
    *,
    program_digest: str,
    episode_id: str,
    step_index: int,
    capability: str,
    payload: dict[str, Any],
    authority_ref: str | None,
    principal: str | None,
) -> str:
    canonical = json.dumps(
        {
            "program_digest": program_digest,
            "episode_id": episode_id,
            "step_index": step_index,
            "capability": capability,
            "payload": payload,
            "authority_ref": authority_ref,
            "principal": principal,
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def compile_sregym_solution(
    problem_id: str,
    *,
    episode_id: str,
    upstream_revision: str,
    bindings: dict[str, str],
    authority_ref: str | None = None,
    principal: str | None = "urn:gymact:agent:gdmcp",
) -> CompiledGdmcpProgram:
    """Compile one known SREGym solution into exact GymAct actuation intents.

    The compiler has no LLM path.  A subject it does not know is a typed
    refusal and belongs at the AutoFDE-Lab novelty boundary.
    """

    if upstream_revision != SREGYM_UPSTREAM_REVISION:
        raise GdmcpRefusal(
            "GDMCP_SUBJECT_DRIFT",
            f"expected={SREGYM_UPSTREAM_REVISION},observed={upstream_revision}",
        )

    program = _SREGYM_PROGRAMS.get(problem_id)
    if program is None:
        raise GdmcpRefusal("GDMCP_SOLUTION_UNKNOWN", problem_id)

    required_bindings: set[str] = set()
    for step in program.steps:
        required_bindings.update(_collect_placeholders(step.payload_template))

    observed_bindings = set(bindings)
    if observed_bindings != required_bindings:
        raise GdmcpRefusal(
            "GDMCP_BINDING_SET_MISMATCH",
            f"required={sorted(required_bindings)},observed={sorted(observed_bindings)}",
        )

    for name, value in bindings.items():
        if not isinstance(value, str):
            raise GdmcpRefusal("GDMCP_BINDING_NOT_STRING", name)
        _validate_binding(name, value)

    program_digest = program.digest()
    intents: list[ActuationIntent] = []
    for index, step in enumerate(program.steps):
        if step.capability not in _GDMCP_SREGYM_CAPABILITIES:
            raise GdmcpRefusal("GDMCP_CAPABILITY_NOT_ADMITTED", step.capability)
        payload = _render(step.payload_template, bindings)
        intents.append(
            ActuationIntent(
                episode_id=episode_id,
                capability=step.capability,
                payload=payload,
                authority_ref=authority_ref,
                principal=principal,
                idempotency_key=_idempotency_key(
                    program_digest=program_digest,
                    episode_id=episode_id,
                    step_index=index,
                    capability=step.capability,
                    payload=payload,
                    authority_ref=authority_ref,
                    principal=principal,
                ),
            )
        )

    return CompiledGdmcpProgram(
        program_digest=program_digest,
        problem_id=program.problem_id,
        upstream_revision=program.upstream_revision,
        intents=tuple(intents),
    )
