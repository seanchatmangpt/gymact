from __future__ import annotations

from dataclasses import dataclass

from .refusal import IndependentVerifierRefusal


@dataclass(frozen=True)
class AuthorityDecision:
    action: str
    broker: str | None
    allowed: bool


def admit_authority(action: str, broker: str | None = None) -> AuthorityDecision:
    normalized = action.upper()
    if normalized in {"OBSERVE", "SELECT", "CONSTRUCT", "VERIFY"}:
        return AuthorityDecision(normalized, broker, True)
    if normalized == "DO" and broker == "BRCE":
        return AuthorityDecision(normalized, broker, True)
    if normalized == "DO":
        raise IndependentVerifierRefusal("UNBROKERED_DO", "consequential DO requires broker=BRCE")
    raise IndependentVerifierRefusal("UNKNOWN_AUTHORITY", normalized)
