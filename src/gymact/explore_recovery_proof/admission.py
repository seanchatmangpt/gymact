from __future__ import annotations

from dataclasses import dataclass

from .attempt import RecoveryAttempt
from .context import RecoveryContext
from .strategies import RecoveryProtocol, decide
from .subject import Refusal
from .witness import CompatibilityWitness


@dataclass(frozen=True, slots=True)
class Admission:
    admitted: bool
    standing: str
    reason: str


def admit(
    attempt: RecoveryAttempt,
    base: RecoveryContext,
    target: RecoveryContext,
    current: RecoveryContext,
    protocol: RecoveryProtocol,
    witness: CompatibilityWitness | None = None,
) -> Admission:
    if attempt.base_fingerprint != base.fingerprint:
        raise Refusal("REFUSED_STALE_RECOVERY_BASE")
    if attempt.target_fingerprint != target.fingerprint:
        raise Refusal("REFUSED_STALE_RECOVERY_TARGET")
    if target.generation < base.generation:
        raise Refusal("REFUSED_NON_MONOTONE_RECOVERY")
    decision = decide(protocol, attempt, current, witness)
    if not decision.admissible:
        raise Refusal(f"REFUSED_RECOVERY_{decision.reason}")
    return Admission(True, decision.standing, decision.reason)
