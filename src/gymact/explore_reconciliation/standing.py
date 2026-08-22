from __future__ import annotations

from .observation import Observation


def standing(observations: tuple[Observation, ...]) -> str:
    outcomes = {observation.outcome for observation in observations}
    if "FAIL" in outcomes:
        return "BUILD_BROKEN"
    if "PENDING" in outcomes:
        return "UNKNOWN"
    if "UNSUPPORTED" in outcomes:
        return "UNSUPPORTED"
    if not observations or "UNKNOWN" in outcomes:
        return "UNKNOWN"
    if outcomes == {"PASS"}:
        return "PARTIAL_ALIVE"
    return "UNKNOWN"
