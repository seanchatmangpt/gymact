from __future__ import annotations

from .refusal import Refused

NON_CONSEQUENTIAL = frozenset({"OBSERVE", "SELECT", "CONSTRUCT", "VERIFY"})

def admit_authority(action: str, broker: str | None = None) -> None:
    if action in NON_CONSEQUENTIAL:
        return
    if action == "DO" and broker == "BRCE":
        return
    if action == "DO":
        raise Refused("DO_REQUIRES_BRCE")
    raise Refused("UNKNOWN_AUTHORITY", action)
