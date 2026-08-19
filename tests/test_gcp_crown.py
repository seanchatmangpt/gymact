from __future__ import annotations

from gymact.gyms.gcp_behavior import GcpBehaviorCoverage
from gymact.gyms.gcp_crown import evaluate_gcp_exactness
from gymact.gyms.gcp_exact import GcpCoverageReport
from gymact.gyms.gcp_sources import GcpSourceAdmissionReport
from gymact.gyms.gcp_validation import GcpValidationCoverage


def method_report(*, exact: bool) -> GcpCoverageReport:
    return GcpCoverageReport(
        admitted_methods=1,
        alive_methods=1 if exact else 0,
        partial_methods=0 if exact else 1,
        unknown_methods=0,
        blocked_methods=0,
        unsupported_methods=0,
        refused_methods=0,
    )


def source_report(*, complete: bool) -> GcpSourceAdmissionReport:
    return GcpSourceAdmissionReport(
        required_sources=10,
        alive_sources=10 if complete else 2,
        missing_sources=() if complete else ("service-config",),
        duplicate_sources=(),
        unreceipted_sources=(),
        empty_sources=(),
        non_alive_sources=(),
        graph_digest_blake3="a" * 64,
    )


def behavior_report(*, complete: bool) -> GcpBehaviorCoverage:
    return GcpBehaviorCoverage(
        admitted_methods=1,
        structurally_executable_methods=1 if complete else 0,
        custom_methods=() if complete else ("example:v1:widgets.rotate",),
        empirically_admitted_methods=(),
        missing_rule_methods=(),
    )


def validation_report(*, exact: bool) -> GcpValidationCoverage:
    return GcpValidationCoverage(
        required_cases=4,
        alive_cases=4 if exact else 3,
        partial_cases=0 if exact else 1,
        unknown_cases=0,
        blocked_cases=0,
        unsupported_cases=0,
        refused_cases=0,
        missing_cases=(),
        duplicate_cases=(),
        unpaired_cases=(),
        divergent_cases=(),
    )


def test_method_complete_does_not_mean_whole_gcp_exact() -> None:
    crown = evaluate_gcp_exactness(
        method_report(exact=True),
        source_report(complete=False),
        behavior_report(complete=True),
        validation_report(exact=True),
    )
    assert not crown.exact
    assert crown.standing == "PARTIAL_ALIVE"
    assert "CONTRACT_SOURCE_FAMILIES_MISSING" in crown.falsifiers


def test_source_complete_does_not_replace_differential_method_coverage() -> None:
    crown = evaluate_gcp_exactness(
        method_report(exact=False),
        source_report(complete=True),
        behavior_report(complete=True),
        validation_report(exact=True),
    )
    assert not crown.exact
    assert crown.standing == "PARTIAL_ALIVE"
    assert crown.falsifiers == ("METHOD_DIFFERENTIAL_COVERAGE_OPEN",)


def test_old_callers_cannot_inherit_new_exact_crown() -> None:
    crown = evaluate_gcp_exactness(method_report(exact=True), source_report(complete=True))
    assert not crown.exact
    assert crown.standing == "PARTIAL_ALIVE"
    assert crown.falsifiers == (
        "SIMULATOR_BEHAVIOR_COVERAGE_UNOBSERVED",
        "VALIDATION_CASE_COVERAGE_UNOBSERVED",
    )


def test_behavior_gap_blocks_exactness_even_with_other_rails_green() -> None:
    crown = evaluate_gcp_exactness(
        method_report(exact=True),
        source_report(complete=True),
        behavior_report(complete=False),
        validation_report(exact=True),
    )
    assert not crown.exact
    assert crown.falsifiers == ("SIMULATOR_BEHAVIOR_COVERAGE_OPEN",)


def test_validation_gap_blocks_exactness_even_with_method_happy_path_green() -> None:
    crown = evaluate_gcp_exactness(
        method_report(exact=True),
        source_report(complete=True),
        behavior_report(complete=True),
        validation_report(exact=False),
    )
    assert not crown.exact
    assert crown.falsifiers == ("VALIDATION_CASE_COVERAGE_OPEN",)


def test_whole_gcp_exactness_requires_all_four_closed() -> None:
    crown = evaluate_gcp_exactness(
        method_report(exact=True),
        source_report(complete=True),
        behavior_report(complete=True),
        validation_report(exact=True),
    )
    assert crown.exact
    assert crown.standing == "ALIVE"
    assert crown.falsifiers == ()
