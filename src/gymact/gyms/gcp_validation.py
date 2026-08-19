"""Generated validation-case topology for whole-GCP exactness.

Method-level coverage is necessary but insufficient: the same method can match
on its happy path while diverging on denial, invalid input, quota, pagination,
long-running-operation, or update-mask semantics.  This module expands the
admitted method/behavior graph into deterministic validation cases and only
promotes a case when real-GCP and simulator observations are both receipted and
equivalent.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Iterable

from blake3 import blake3

from gymact.gyms.gcp_behavior import GcpBehaviorEffect, GcpBehaviorRule
from gymact.gyms.gcp_exact import GcpObservation

__all__ = [
    "GcpValidationCase",
    "GcpValidationCaseKind",
    "GcpValidationCoverage",
    "GcpValidationEvidence",
    "build_validation_plan",
    "evaluate_validation_coverage",
]


class GcpValidationCaseKind(StrEnum):
    HAPPY_PATH = "HAPPY_PATH"
    INVALID_ARGUMENT = "INVALID_ARGUMENT"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    SERVICE_DISABLED = "SERVICE_DISABLED"
    NOT_FOUND = "NOT_FOUND"
    ALREADY_EXISTS = "ALREADY_EXISTS"
    QUOTA_EXHAUSTED = "QUOTA_EXHAUSTED"
    PAGINATION = "PAGINATION"
    UPDATE_MASK = "UPDATE_MASK"
    LRO_SUBMIT = "LRO_SUBMIT"
    LRO_POLL = "LRO_POLL"
    LRO_CANCEL = "LRO_CANCEL"
    LRO_DELETE = "LRO_DELETE"
    LRO_WAIT = "LRO_WAIT"
    EXACT_REPLAY = "EXACT_REPLAY"


@dataclass(frozen=True, slots=True)
class GcpValidationCase:
    method_id: str
    kind: GcpValidationCaseKind

    @property
    def identity(self) -> str:
        return f"{self.method_id}#{self.kind.value}"

    @property
    def digest_blake3(self) -> str:
        return blake3(self.identity.encode()).hexdigest()


@dataclass(frozen=True, slots=True)
class GcpValidationEvidence:
    case_id: str
    real_observation: GcpObservation | None
    simulator_observation: GcpObservation | None
    real_receipt: str | None
    simulator_receipt: str | None
    standing: str

    @property
    def paired(self) -> bool:
        return bool(
            self.real_observation
            and self.simulator_observation
            and self.real_receipt
            and self.simulator_receipt
        )

    @property
    def equivalent(self) -> bool:
        return bool(
            self.paired
            and self.real_observation is not None
            and self.simulator_observation is not None
            and self.real_observation.digest_blake3 == self.simulator_observation.digest_blake3
        )

    @property
    def alive(self) -> bool:
        return self.standing == "ALIVE" and self.equivalent


@dataclass(frozen=True, slots=True)
class GcpValidationCoverage:
    required_cases: int
    alive_cases: int
    partial_cases: int
    unknown_cases: int
    blocked_cases: int
    unsupported_cases: int
    refused_cases: int
    missing_cases: tuple[str, ...]
    duplicate_cases: tuple[str, ...]
    unpaired_cases: tuple[str, ...]
    divergent_cases: tuple[str, ...]

    @property
    def exact(self) -> bool:
        return (
            self.required_cases > 0
            and self.alive_cases == self.required_cases
            and self.partial_cases == 0
            and self.unknown_cases == 0
            and self.blocked_cases == 0
            and self.unsupported_cases == 0
            and self.refused_cases == 0
            and not self.missing_cases
            and not self.duplicate_cases
            and not self.unpaired_cases
            and not self.divergent_cases
        )


def _requires_not_found(effect: GcpBehaviorEffect) -> bool:
    return effect in {
        GcpBehaviorEffect.READ_ONE,
        GcpBehaviorEffect.REPLACE,
        GcpBehaviorEffect.PATCH,
        GcpBehaviorEffect.DELETE,
        GcpBehaviorEffect.IAM_GET,
        GcpBehaviorEffect.IAM_SET,
        GcpBehaviorEffect.IAM_TEST,
        GcpBehaviorEffect.OPERATION_GET,
        GcpBehaviorEffect.OPERATION_CANCEL,
        GcpBehaviorEffect.OPERATION_DELETE,
        GcpBehaviorEffect.OPERATION_WAIT,
    }


def _is_mutating(effect: GcpBehaviorEffect) -> bool:
    return effect not in {
        GcpBehaviorEffect.READ_ONE,
        GcpBehaviorEffect.READ_MANY,
        GcpBehaviorEffect.IAM_GET,
        GcpBehaviorEffect.IAM_TEST,
        GcpBehaviorEffect.OPERATION_GET,
        GcpBehaviorEffect.OPERATION_LIST,
        GcpBehaviorEffect.OPERATION_WAIT,
    }


def build_validation_plan(rules: Iterable[GcpBehaviorRule]) -> tuple[GcpValidationCase, ...]:
    """Expand each admitted method into the minimum falsifying case topology.

    Cases are derived from observable consequence families, not service names.
    This preserves DfCM closure: a newly discovered method automatically gains
    the same applicable falsifiers without another hand-written test matrix.
    """

    cases: set[GcpValidationCase] = set()
    seen_methods: set[str] = set()
    for rule in rules:
        if rule.method_id in seen_methods:
            raise ValueError(f"DUPLICATE_BEHAVIOR_RULE:{rule.method_id}")
        seen_methods.add(rule.method_id)
        cases.add(GcpValidationCase(rule.method_id, GcpValidationCaseKind.HAPPY_PATH))
        cases.add(GcpValidationCase(rule.method_id, GcpValidationCaseKind.INVALID_ARGUMENT))
        cases.add(GcpValidationCase(rule.method_id, GcpValidationCaseKind.PERMISSION_DENIED))
        cases.add(GcpValidationCase(rule.method_id, GcpValidationCaseKind.SERVICE_DISABLED))

        if _requires_not_found(rule.effect):
            cases.add(GcpValidationCase(rule.method_id, GcpValidationCaseKind.NOT_FOUND))
        if rule.effect is GcpBehaviorEffect.CREATE:
            cases.add(GcpValidationCase(rule.method_id, GcpValidationCaseKind.ALREADY_EXISTS))
        if _is_mutating(rule.effect):
            cases.add(GcpValidationCase(rule.method_id, GcpValidationCaseKind.QUOTA_EXHAUSTED))
        if rule.effect is GcpBehaviorEffect.READ_MANY:
            cases.add(GcpValidationCase(rule.method_id, GcpValidationCaseKind.PAGINATION))
        if rule.effect is GcpBehaviorEffect.PATCH:
            cases.add(GcpValidationCase(rule.method_id, GcpValidationCaseKind.UPDATE_MASK))
        if rule.long_running:
            for kind in (
                GcpValidationCaseKind.LRO_SUBMIT,
                GcpValidationCaseKind.LRO_POLL,
                GcpValidationCaseKind.LRO_CANCEL,
                GcpValidationCaseKind.LRO_DELETE,
                GcpValidationCaseKind.LRO_WAIT,
            ):
                cases.add(GcpValidationCase(rule.method_id, kind))
        if rule.effect is GcpBehaviorEffect.CUSTOM or rule.empirically_admitted:
            cases.add(GcpValidationCase(rule.method_id, GcpValidationCaseKind.EXACT_REPLAY))

    return tuple(sorted(cases, key=lambda case: case.identity))


def evaluate_validation_coverage(
    required: Iterable[GcpValidationCase],
    evidence: Iterable[GcpValidationEvidence],
) -> GcpValidationCoverage:
    required_tuple = tuple(required)
    required_ids = {case.identity for case in required_tuple}
    if len(required_ids) != len(required_tuple):
        raise ValueError("DUPLICATE_REQUIRED_VALIDATION_CASE")

    grouped: dict[str, list[GcpValidationEvidence]] = {}
    for item in evidence:
        grouped.setdefault(item.case_id, []).append(item)

    duplicate = tuple(sorted(case_id for case_id, items in grouped.items() if len(items) > 1))
    extras = sorted(set(grouped) - required_ids)
    if extras:
        raise ValueError(f"VALIDATION_EVIDENCE_CASE_NOT_ADMITTED:{','.join(extras)}")
    missing = tuple(sorted(required_ids - set(grouped)))

    alive = partial = unknown = blocked = unsupported = refused = 0
    unpaired: list[str] = []
    divergent: list[str] = []
    for case_id in sorted(required_ids & set(grouped)):
        items = grouped[case_id]
        if len(items) != 1:
            continue
        item = items[0]
        if not item.paired:
            unpaired.append(case_id)
        elif not item.equivalent:
            divergent.append(case_id)
        if item.alive:
            alive += 1
        elif item.standing == "PARTIAL_ALIVE":
            partial += 1
        elif item.standing == "BLOCKED":
            blocked += 1
        elif item.standing == "UNSUPPORTED":
            unsupported += 1
        elif item.standing == "REFUSED":
            refused += 1
        else:
            unknown += 1

    return GcpValidationCoverage(
        required_cases=len(required_ids),
        alive_cases=alive,
        partial_cases=partial,
        unknown_cases=unknown,
        blocked_cases=blocked,
        unsupported_cases=unsupported,
        refused_cases=refused,
        missing_cases=missing,
        duplicate_cases=duplicate,
        unpaired_cases=tuple(unpaired),
        divergent_cases=tuple(divergent),
    )
