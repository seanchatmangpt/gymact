from dataclasses import dataclass


@dataclass(frozen=True)
class FailureWorld:
    name: str
    expected_refusal: str


def canonical_worlds() -> tuple[FailureWorld, ...]:
    return (
        FailureWorld("subject-drift", "SUBJECT_DRIFT"),
        FailureWorld("solver-divergence", "SOLVER_DIVERGENCE"),
        FailureWorld("duality-gap", "NONZERO_DUALITY_GAP"),
        FailureWorld("oracle-divergence", "ORACLE_DIVERGENCE"),
        FailureWorld("runtime-mismatch", "RUNTIME_MISMATCH"),
        FailureWorld("stale-certificate", "STALE_CERTIFICATE"),
        FailureWorld("ambient-do", "UNRECEIPTED_ACTUATION"),
        FailureWorld("receipt-tamper", "RECEIPT_DRIFT"),
    )
