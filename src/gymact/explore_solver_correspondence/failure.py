from __future__ import annotations

from dataclasses import dataclass

@dataclass(frozen=True)
class FailureCase:
    kind: str
    expected: str


def failure_worlds() -> tuple[FailureCase, ...]:
    return (
        FailureCase("subject-drift", "REFUSED[SUBJECT_DIVERGENCE]"),
        FailureCase("engine-collapse", "REFUSED[PSEUDO_INDEPENDENT_ENGINE]"),
        FailureCase("value-divergence", "REFUSED[OPTIMAL_VALUE_DIVERGENCE]"),
        FailureCase("common-cause", "REFUSED[COMMON_CAUSE_EVIDENCE]"),
        FailureCase("pseudo-quorum", "REFUSED[PSEUDO_QUORUM]"),
        FailureCase("direct-do", "REFUSED[DO_REQUIRES_BRCE]"),
        FailureCase("receipt-tamper", "REFUSED[RECEIPT_DRIFT]"),
    )
