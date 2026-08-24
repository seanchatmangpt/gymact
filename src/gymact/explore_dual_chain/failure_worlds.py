from dataclasses import dataclass

@dataclass(frozen=True)
class FailureWorld:
    name: str
    expected_refusal: str

WORLDS = (
    FailureWorld("subject_drift", "INVALID_SUBJECT"),
    FailureWorld("engine_alias", "PSEUDO_INDEPENDENT_ENGINE"),
    FailureWorld("dual_infeasible", "DUAL_INFEASIBLE"),
    FailureWorld("duality_gap", "STRONG_DUALITY_GAP"),
    FailureWorld("pseudo_quorum", "PSEUDO_QUORUM"),
    FailureWorld("ambient_do", "UNRECEIPTED_ACTUATION"),
    FailureWorld("receipt_drift", "RECEIPT_DRIFT"),
)
