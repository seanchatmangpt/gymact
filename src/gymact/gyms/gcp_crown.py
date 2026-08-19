"""Whole-GCP exactness crown.

A method census can be complete inside its own admitted REST scope without
proving GCP as a whole. This module is the only whole-GCP promotion boundary:
both differential method coverage and the complete multi-source contract graph
must close.
"""

from __future__ import annotations

from dataclasses import dataclass

from gymact.gyms.gcp_exact import GcpCoverageReport
from gymact.gyms.gcp_sources import GcpSourceAdmissionReport

__all__ = ["GcpExactnessCrown", "evaluate_gcp_exactness"]


@dataclass(frozen=True, slots=True)
class GcpExactnessCrown:
    method_coverage: GcpCoverageReport
    source_admission: GcpSourceAdmissionReport

    @property
    def exact(self) -> bool:
        return self.method_coverage.exact and self.source_admission.complete

    @property
    def standing(self) -> str:
        if self.exact:
            return "ALIVE"
        if (
            self.method_coverage.alive_methods > 0
            or self.source_admission.alive_sources > 0
        ):
            return "PARTIAL_ALIVE"
        return "UNKNOWN"

    @property
    def falsifiers(self) -> tuple[str, ...]:
        failures: list[str] = []
        if not self.method_coverage.exact:
            failures.append("METHOD_DIFFERENTIAL_COVERAGE_OPEN")
        if self.source_admission.missing_sources:
            failures.append("CONTRACT_SOURCE_FAMILIES_MISSING")
        if self.source_admission.duplicate_sources:
            failures.append("CONTRACT_SOURCE_FAMILIES_DUPLICATED")
        if self.source_admission.unreceipted_sources:
            failures.append("CONTRACT_SOURCE_EVIDENCE_UNRECEIPTED")
        if self.source_admission.empty_sources:
            failures.append("CONTRACT_SOURCE_EVIDENCE_EMPTY")
        if self.source_admission.non_alive_sources:
            failures.append("CONTRACT_SOURCE_FAMILY_NOT_ALIVE")
        return tuple(failures)


def evaluate_gcp_exactness(
    method_coverage: GcpCoverageReport,
    source_admission: GcpSourceAdmissionReport,
) -> GcpExactnessCrown:
    return GcpExactnessCrown(
        method_coverage=method_coverage,
        source_admission=source_admission,
    )
