def compatible(required: set[str], provided: set[str]) -> bool:
    return required <= provided


def missing(required: set[str], provided: set[str]) -> tuple[str, ...]:
    return tuple(sorted(required - provided))
