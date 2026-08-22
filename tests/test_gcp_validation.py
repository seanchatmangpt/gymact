from __future__ import annotations

import pytest

from gymact.gyms.gcp_behavior import GcpBehaviorEffect, GcpBehaviorRule
from gymact.gyms.gcp_exact import GcpObservation
from gymact.gyms.gcp_validation import (
    GcpValidationCaseKind,
    GcpValidationEvidence,
    build_validation_plan,
    evaluate_validation_coverage,
)


def _rule(
    method_id: str,
    effect: GcpBehaviorEffect,
    *,
    response_schema: str | None = "Resource",
    source: str = "DISCOVERY_INFERRED",
    receipt: str | None = None,
) -> GcpBehaviorRule:
    return GcpBehaviorRule(
        method_id=method_id,
        effect=effect,
        http_method="GET" if effect in {GcpBehaviorEffect.READ_ONE, GcpBehaviorEffect.READ_MANY} else "POST",
        path="v1/{name}",
        response_schema=response_schema,
        source=source,
        evidence_receipt=receipt,
    )


def _observation(digest: str) -> GcpObservation:
    return GcpObservation(
        status_code=200,
        headers=(("content-type", "application/json"),),
        body_kind="json",
        canonical_body="{}",
        digest_blake3=digest,
    )


def test_validation_plan_expands_behavior_not_service_names() -> None:
    rules = (
        _rule("api:v1:widgets.get", GcpBehaviorEffect.READ_ONE),
        _rule("api:v1:widgets.list", GcpBehaviorEffect.READ_MANY),
        _rule("api:v1:widgets.create", GcpBehaviorEffect.CREATE),
        _rule("api:v1:widgets.patch", GcpBehaviorEffect.PATCH),
        _rule("api:v1:widgets.asyncCreate", GcpBehaviorEffect.CREATE, response_schema="Operation"),
        _rule("api:v1:widgets.rotate", GcpBehaviorEffect.CUSTOM),
    )
    plan = build_validation_plan(rules)
    kinds = {(case.method_id, case.kind) for case in plan}

    for rule in rules:
        for universal in (
            GcpValidationCaseKind.HAPPY_PATH,
            GcpValidationCaseKind.INVALID_ARGUMENT,
            GcpValidationCaseKind.PERMISSION_DENIED,
            GcpValidationCaseKind.SERVICE_DISABLED,
        ):
            assert (rule.method_id, universal) in kinds

    assert ("api:v1:widgets.get", GcpValidationCaseKind.NOT_FOUND) in kinds
    assert ("api:v1:widgets.list", GcpValidationCaseKind.PAGINATION) in kinds
    assert ("api:v1:widgets.create", GcpValidationCaseKind.ALREADY_EXISTS) in kinds
    assert ("api:v1:widgets.create", GcpValidationCaseKind.QUOTA_EXHAUSTED) in kinds
    assert ("api:v1:widgets.patch", GcpValidationCaseKind.UPDATE_MASK) in kinds
    for lro_kind in (
        GcpValidationCaseKind.LRO_SUBMIT,
        GcpValidationCaseKind.LRO_POLL,
        GcpValidationCaseKind.LRO_CANCEL,
        GcpValidationCaseKind.LRO_DELETE,
        GcpValidationCaseKind.LRO_WAIT,
    ):
        assert ("api:v1:widgets.asyncCreate", lro_kind) in kinds
    assert ("api:v1:widgets.rotate", GcpValidationCaseKind.EXACT_REPLAY) in kinds


def test_validation_plan_refuses_duplicate_behavior_subjects() -> None:
    rule = _rule("api:v1:widgets.get", GcpBehaviorEffect.READ_ONE)
    with pytest.raises(ValueError, match="DUPLICATE_BEHAVIOR_RULE"):
        build_validation_plan((rule, rule))


def test_case_coverage_requires_unique_paired_equivalent_receipts() -> None:
    required = build_validation_plan((_rule("api:v1:widgets.get", GcpBehaviorEffect.READ_ONE),))
    evidence = tuple(
        GcpValidationEvidence(
            case_id=case.identity,
            real_observation=_observation("a" * 64),
            simulator_observation=_observation("a" * 64),
            real_receipt=f"real:{case.digest_blake3}",
            simulator_receipt=f"sim:{case.digest_blake3}",
            standing="ALIVE",
        )
        for case in required
    )
    coverage = evaluate_validation_coverage(required, evidence)
    assert coverage.exact
    assert coverage.alive_cases == coverage.required_cases


def test_missing_unpaired_divergent_and_duplicate_cases_all_block_exactness() -> None:
    required = build_validation_plan((_rule("api:v1:widgets.get", GcpBehaviorEffect.READ_ONE),))
    first, second, third, *rest = required
    evidence = [
        GcpValidationEvidence(
            case_id=first.identity,
            real_observation=_observation("a" * 64),
            simulator_observation=_observation("a" * 64),
            real_receipt="real:first",
            simulator_receipt=None,
            standing="PARTIAL_ALIVE",
        ),
        GcpValidationEvidence(
            case_id=second.identity,
            real_observation=_observation("a" * 64),
            simulator_observation=_observation("b" * 64),
            real_receipt="real:second",
            simulator_receipt="sim:second",
            standing="ALIVE",
        ),
        GcpValidationEvidence(
            case_id=third.identity,
            real_observation=_observation("a" * 64),
            simulator_observation=_observation("a" * 64),
            real_receipt="real:third:1",
            simulator_receipt="sim:third:1",
            standing="ALIVE",
        ),
        GcpValidationEvidence(
            case_id=third.identity,
            real_observation=_observation("a" * 64),
            simulator_observation=_observation("a" * 64),
            real_receipt="real:third:2",
            simulator_receipt="sim:third:2",
            standing="ALIVE",
        ),
    ]
    for case in rest[:-1]:
        evidence.append(
            GcpValidationEvidence(
                case_id=case.identity,
                real_observation=_observation("a" * 64),
                simulator_observation=_observation("a" * 64),
                real_receipt=f"real:{case.digest_blake3}",
                simulator_receipt=f"sim:{case.digest_blake3}",
                standing="ALIVE",
            )
        )
    coverage = evaluate_validation_coverage(required, evidence)
    assert not coverage.exact
    assert first.identity in coverage.unpaired_cases
    assert second.identity in coverage.divergent_cases
    assert third.identity in coverage.duplicate_cases
    assert rest[-1].identity in coverage.missing_cases


def test_evidence_for_non_admitted_case_is_refused() -> None:
    required = build_validation_plan((_rule("api:v1:widgets.get", GcpBehaviorEffect.READ_ONE),))
    extra = GcpValidationEvidence(
        case_id="other:v1:x#HAPPY_PATH",
        real_observation=_observation("a" * 64),
        simulator_observation=_observation("a" * 64),
        real_receipt="real",
        simulator_receipt="sim",
        standing="ALIVE",
    )
    with pytest.raises(ValueError, match="VALIDATION_EVIDENCE_CASE_NOT_ADMITTED"):
        evaluate_validation_coverage(required, (extra,))
