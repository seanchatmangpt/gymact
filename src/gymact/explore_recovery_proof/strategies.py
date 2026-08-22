from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .attempt import RecoveryAttempt
from .context import RecoveryContext
from .witness import CompatibilityWitness, WitnessKind


class RecoveryProtocol(StrEnum):
    CAS_RESELECT = "CAS_RESELECT"
    VALIDATE_REBIND = "VALIDATE_REBIND"
    REQUALIFY_ONLY = "REQUALIFY_ONLY"


@dataclass(frozen=True, slots=True)
class ProtocolDecision:
    protocol: RecoveryProtocol
    admissible: bool
    standing: str
    reason: str


def decide(
    protocol: RecoveryProtocol,
    attempt: RecoveryAttempt,
    current: RecoveryContext,
    witness: CompatibilityWitness | None = None,
) -> ProtocolDecision:
    if protocol is RecoveryProtocol.CAS_RESELECT:
        admitted = attempt.target_fingerprint == current.fingerprint
        return ProtocolDecision(
            protocol,
            admitted,
            "REQUALIFYING" if admitted else "UNKNOWN",
            "TARGET_CURRENT" if admitted else "STALE_TARGET",
        )
    if protocol is RecoveryProtocol.VALIDATE_REBIND:
        admitted = bool(
            witness
            and witness.after_fingerprint == current.fingerprint
            and witness.kind in {WitnessKind.EXACT, WitnessKind.SEMANTIC_EQUIVALENT}
        )
        return ProtocolDecision(
            protocol,
            admitted,
            "REQUALIFYING" if admitted else "UNKNOWN",
            "EQUIVALENCE_WITNESS" if admitted else "WITNESS_REQUIRED",
        )
    return ProtocolDecision(protocol, True, "REQUALIFYING", "FULL_REQUALIFICATION")
