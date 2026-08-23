from __future__ import annotations

_ALLOWED = frozenset({"OBSERVE", "SELECT", "CONSTRUCT", "VERIFY"})


def require_explore_authority(action: str, *, brce_receipted: bool = False) -> str:
    if action in _ALLOWED:
        return action
    if action == "DO" and not brce_receipted:
        raise ValueError("REFUSED_UNRECEIPTED_ACTUATION")
    if action == "DO" and brce_receipted:
        raise ValueError("REFUSED_EXPLORE_DO_OUTSIDE_BRCE_OWNER")
    raise ValueError("REFUSED_UNKNOWN_AUTHORITY_ACTION")
