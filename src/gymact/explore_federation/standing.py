def standing(outcomes: list[str]) -> str:
    if not outcomes:
        return "UNKNOWN"
    if "FAIL" in outcomes:
        return "BUILD_BROKEN"
    if "PENDING" in outcomes or "UNKNOWN" in outcomes:
        return "UNKNOWN"
    if all(outcome == "UNSUPPORTED" for outcome in outcomes):
        return "UNSUPPORTED"
    return "PARTIAL_ALIVE"
