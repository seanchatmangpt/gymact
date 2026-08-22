def standing(outcomes):
    values = set(outcomes)
    if "FAIL" in values:
        return "BUILD_BROKEN"
    if "BLOCKED" in values:
        return "BLOCKED"
    if not values or values <= {"UNKNOWN", "UNSUPPORTED", "PENDING"}:
        return "UNKNOWN"
    return "PARTIAL_ALIVE"
