def collection_boundary(collected: int, errors: int, skipped: int = 0):
    if errors < 0 or collected < 0 or skipped < 0:
        raise ValueError("REFUSED_INVALID_COLLECTION_COUNTS")
    if errors:
        return "BUILD_BROKEN"
    if collected == 0:
        return "UNKNOWN"
    return "PARTIAL_ALIVE"
