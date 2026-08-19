"""Contract-to-behavior compilation for the GCP exact simulator.

Discovery describes method identity, transport shape, schemas and scopes but not
all runtime semantics.  This module compiles the structural behavior that *is*
derivable without pretending inference is empirical proof.  Custom actions stay
``CUSTOM`` unless an empirical rule receipt explicitly admits them.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Iterable

from gymact.gyms.gcp_exact import DiscoveryMethod, GcpContractCensus

__all__ = [
    "GcpBehaviorCoverage",
    "GcpBehaviorEffect",
    "GcpBehaviorRule",
    "compile_behavior_corpus",
    "compile_behavior_rule",
]


class GcpBehaviorEffect(StrEnum):
    READ_ONE = "READ_ONE"
    READ_MANY = "READ_MANY"
    CREATE = "CREATE"
    REPLACE = "REPLACE"
    PATCH = "PATCH"
    DELETE = "DELETE"
    IAM_GET = "IAM_GET"
    IAM_SET = "IAM_SET"
    IAM_TEST = "IAM_TEST"
    SERVICE_ENABLE = "SERVICE_ENABLE"
    SERVICE_DISABLE = "SERVICE_DISABLE"
    OPERATION_GET = "OPERATION_GET"
    OPERATION_LIST = "OPERATION_LIST"
    OPERATION_CANCEL = "OPERATION_CANCEL"
    OPERATION_DELETE = "OPERATION_DELETE"
    OPERATION_WAIT = "OPERATION_WAIT"
    CUSTOM = "CUSTOM"


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


@dataclass(frozen=True, slots=True)
class GcpBehaviorRule:
    method_id: str
    effect: GcpBehaviorEffect
    http_method: str
    path: str
    response_schema: str | None
    source: str = "DISCOVERY_INFERRED"
    evidence_receipt: str | None = None

    @property
    def read_only(self) -> bool:
        return self.effect in _READ_EFFECTS

    @property
    def long_running(self) -> bool:
        schema = (self.response_schema or "").lower()
        return (
            self.effect
            in {
                GcpBehaviorEffect.CREATE,
                GcpBehaviorEffect.REPLACE,
                GcpBehaviorEffect.PATCH,
                GcpBehaviorEffect.DELETE,
                GcpBehaviorEffect.SERVICE_ENABLE,
                GcpBehaviorEffect.SERVICE_DISABLE,
                GcpBehaviorEffect.CUSTOM,
            }
            and (schema == "operation" or schema.endswith("operation"))
        )

    @property
    def empirically_admitted(self) -> bool:
        return self.source == "EMPIRICAL" and bool(self.evidence_receipt)

    @property
    def structurally_executable(self) -> bool:
        return self.effect is not GcpBehaviorEffect.CUSTOM or self.empirically_admitted

    def with_empirical_admission(self, receipt: str) -> "GcpBehaviorRule":
        if not receipt:
            raise ValueError("EMPIRICAL_BEHAVIOR_RECEIPT_REQUIRED")
        return GcpBehaviorRule(
            method_id=self.method_id,
            effect=self.effect,
            http_method=self.http_method,
            path=self.path,
            response_schema=self.response_schema,
            source="EMPIRICAL",
            evidence_receipt=receipt,
        )


@dataclass(frozen=True, slots=True)
class GcpBehaviorCoverage:
    admitted_methods: int
    structurally_executable_methods: int
    custom_methods: tuple[str, ...]
    empirically_admitted_methods: tuple[str, ...]
    missing_rule_methods: tuple[str, ...]

    @property
    def structural_complete(self) -> bool:
        return (
            self.admitted_methods > 0
            and self.structurally_executable_methods == self.admitted_methods
            and not self.missing_rule_methods
        )

    @property
    def empirically_exact(self) -> bool:
        return (
            self.admitted_methods > 0
            and len(self.empirically_admitted_methods) == self.admitted_methods
            and not self.missing_rule_methods
        )


def _name(method: DiscoveryMethod) -> str:
    return method.name.replace("_", "").lower()


def _is_operations_surface(method: DiscoveryMethod) -> bool:
    path = f"{method.resource_path}.{method.path}".lower()
    return "operation" in path


def _is_service_usage_surface(method: DiscoveryMethod) -> bool:
    token = f"{method.api}.{method.resource_path}.{method.path}".lower()
    return "serviceusage" in token or "/services/" in token or token.endswith("/services")


def compile_behavior_rule(method: DiscoveryMethod) -> GcpBehaviorRule:
    """Compile only semantics justified by the published method shape.

    The ordering is intentional: protocol-defined IAM/LRO/Service Usage methods
    outrank generic CRUD names. Unknown POST/custom verbs remain CUSTOM rather
    than being guessed into a mutation family.
    """

    name = _name(method)
    verb = method.http_method.upper()

    if name == "getiampolicy":
        effect = GcpBehaviorEffect.IAM_GET
    elif name == "setiampolicy":
        effect = GcpBehaviorEffect.IAM_SET
    elif name == "testiampermissions":
        effect = GcpBehaviorEffect.IAM_TEST
    elif _is_operations_surface(method) and name == "get":
        effect = GcpBehaviorEffect.OPERATION_GET
    elif _is_operations_surface(method) and name == "list":
        effect = GcpBehaviorEffect.OPERATION_LIST
    elif _is_operations_surface(method) and name == "cancel":
        effect = GcpBehaviorEffect.OPERATION_CANCEL
    elif _is_operations_surface(method) and name == "delete":
        effect = GcpBehaviorEffect.OPERATION_DELETE
    elif _is_operations_surface(method) and name == "wait":
        effect = GcpBehaviorEffect.OPERATION_WAIT
    elif _is_service_usage_surface(method) and name in {"enable", "batchenable"}:
        effect = GcpBehaviorEffect.SERVICE_ENABLE
    elif _is_service_usage_surface(method) and name in {"disable", "batchdisable"}:
        effect = GcpBehaviorEffect.SERVICE_DISABLE
    elif name in {"list", "aggregatedlist", "search", "searchallresources"} and verb == "GET":
        effect = GcpBehaviorEffect.READ_MANY
    elif name == "get" and verb == "GET":
        effect = GcpBehaviorEffect.READ_ONE
    elif name in {"create", "insert"} and verb in {"POST", "PUT"}:
        effect = GcpBehaviorEffect.CREATE
    elif name in {"update", "replace"} and verb in {"PUT", "POST"}:
        effect = GcpBehaviorEffect.REPLACE
    elif name in {"patch", "update"} and verb == "PATCH":
        effect = GcpBehaviorEffect.PATCH
    elif name == "delete" and verb == "DELETE":
        effect = GcpBehaviorEffect.DELETE
    elif verb == "GET":
        # A GET cannot lawfully mutate the modeled control-plane state.  Its
        # precise response shape may still require empirical replay, but it is
        # safe to expose as a bounded read rather than a DO surface.
        effect = GcpBehaviorEffect.READ_ONE
    else:
        effect = GcpBehaviorEffect.CUSTOM

    return GcpBehaviorRule(
        method_id=method.identity,
        effect=effect,
        http_method=verb,
        path=method.path,
        response_schema=method.response_schema,
    )


def compile_behavior_corpus(
    census: GcpContractCensus,
    *,
    empirical_rules: Iterable[GcpBehaviorRule] = (),
) -> tuple[tuple[GcpBehaviorRule, ...], GcpBehaviorCoverage]:
    empirical_by_id = {rule.method_id: rule for rule in empirical_rules}
    compiled: list[GcpBehaviorRule] = []
    admitted = census.method_ids

    for method in census.methods:
        inferred = compile_behavior_rule(method)
        empirical = empirical_by_id.get(method.identity)
        if empirical is not None:
            if not empirical.empirically_admitted:
                raise ValueError(f"EMPIRICAL_BEHAVIOR_RULE_UNRECEIPTED:{method.identity}")
            if empirical.http_method != inferred.http_method or empirical.path != inferred.path:
                raise ValueError(f"EMPIRICAL_BEHAVIOR_RULE_SUBJECT_MISMATCH:{method.identity}")
            compiled.append(empirical)
        else:
            compiled.append(inferred)

    extras = sorted(set(empirical_by_id) - admitted)
    if extras:
        raise ValueError(f"EMPIRICAL_BEHAVIOR_RULE_NOT_ADMITTED:{','.join(extras)}")

    by_id = {rule.method_id: rule for rule in compiled}
    missing = tuple(sorted(admitted - set(by_id)))
    custom = tuple(
        sorted(
            rule.method_id
            for rule in compiled
            if rule.effect is GcpBehaviorEffect.CUSTOM and not rule.empirically_admitted
        )
    )
    structural_count = sum(rule.structurally_executable for rule in compiled)
    empirical = tuple(sorted(rule.method_id for rule in compiled if rule.empirically_admitted))
    coverage = GcpBehaviorCoverage(
        admitted_methods=len(admitted),
        structurally_executable_methods=structural_count,
        custom_methods=custom,
        empirically_admitted_methods=empirical,
        missing_rule_methods=missing,
    )
    return tuple(sorted(compiled, key=lambda rule: rule.method_id)), coverage
