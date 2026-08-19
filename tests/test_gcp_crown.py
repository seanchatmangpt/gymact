from __future__ import annotations

from gymact.gyms.gcp_crown import evaluate_gcp_exactness
from gymact.gyms.gcp_exact import GcpCoverageReport
from gymact.gyms.gcp_sources import GcpSourceAdmissionReport


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


def test_method_complete_does_not_mean_whole_gcp_exact() -> None:
    crown = evaluate_gcp_exactness(method_report(exact=True), source_report(complete=False))
    assert not crown.exact
    assert crown.standing == "PARTIAL_ALIVE"
    assert "CONTRACT_SOURCE_FAMILIES_MISSING" in crown.falsifiers


def test_source_complete_does_not_replace_differential_method_coverage() -> None:
    crown = evaluate_gcp_exactness(method_report(exact=False), source_report(complete=True))
    assert not crown.exact
    assert crown.standing == "PARTIAL_ALIVE"
    assert crown.falsifiers == ("METHOD_DIFFERENTIAL_COVERAGE_OPEN",)


def test_whole_gcp_exactness_requires_both_closed() -> None:
    crown = evaluate_gcp_exactness(method_report(exact=True), source_report(complete=True))
    assert crown.exact
    assert crown.standing == "ALIVE"
    assert crown.falsifiers == ()
