"""Whole-GCP exactness crown.

A method census can be complete inside its own admitted REST scope without
proving GCP as a whole. Likewise, a source census can be complete while the
simulator still has unmodeled transitions, and a method-level happy-path match
can hide divergent error/quota/pagination/LRO behavior. This module is the only
whole-GCP promotion boundary: source topology, executable behavior coverage,
method-level differential evidence, and generated validation-case evidence must
all close.
"""

from __future__ import annotations

from dataclasses import dataclass

from gymact.gyms.gcp_behavior import GcpBehaviorCoverage
from gymact.gyms.gcp_exact import GcpCoverageReport
from gymact.gyms.gcp_sources import GcpSourceAdmissionReport
from gymact.gyms.gcp_validation import GcpValidationCoverage

__all__ = ["GcpExactnessCrown", "evaluate_gcp_exactness"]


@dataclass(frozen=True, slots=True)
class GcpExactnessCrown:
    method_coverage: GcpCoverageReport
    source_admission: GcpSourceAdmissionReport
    behavior_coverage: GcpBehaviorCoverage | None
    validation_coverage: GcpValidationCoverage | None

    @property
    def exact(self) -> bool:
        return (
            self.method_coverage.exact
            and self.source_admission.complete
            and self.behavior_coverage is not None
            and self.behavior_coverage.structural_complete
            and self.validation_coverage is not None
            and self.validation_coverage.exact
        )

    @property
    def standing(self) -> str:
        if self.exact:
            return "ALIVE"
        if (
            self.method_coverage.alive_methods > 0
            or self.source_admission.alive_sources > 0
            or (
                self.behavior_coverage is not None
                and self.behavior_coverage.structurally_executable_methods > 0
            )
            or (
                self.validation_coverage is not None
                and self.validation_coverage.alive_cases > 0
            )
        ):
            return "PARTIAL_ALIVE"
        return "UNKNOWN"

    @property
    def falsifiers(self) -> tuple[str, ...]:
        failures: list[str] = []
        if not self.method_coverage.exact:
            failures.append("METHOD_DIFFERENTIAL_COVERAGE_OPEN")
        if self.behavior_coverage is None:
            failures.append("SIMULATOR_BEHAVIOR_COVERAGE_UNOBSERVED")
        elif not self.behavior_coverage.structural_complete:
            failures.append("SIMULATOR_BEHAVIOR_COVERAGE_OPEN")
        if self.validation_coverage is None:
            failures.append("VALIDATION_CASE_COVERAGE_UNOBSERVED")
        elif not self.validation_coverage.exact:
            failures.append("VALIDATION_CASE_COVERAGE_OPEN")
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
    behavior_coverage: GcpBehaviorCoverage | None = None,
    validation_coverage: GcpValidationCoverage | None = None,
) -> GcpExactnessCrown:
    """Evaluate whole-cloud standing without ambient evidence transfer.

    New proof obligations default to ``None`` for compatibility with older
    callers, but absence blocks the crown. Existing integrations therefore
    cannot inherit a stronger ALIVE claim merely because the exactness calculus
    expanded after they were written.
    """

    return GcpExactnessCrown(
        method_coverage=method_coverage,
        source_admission=source_admission,
        behavior_coverage=behavior_coverage,
        validation_coverage=validation_coverage,
    )
