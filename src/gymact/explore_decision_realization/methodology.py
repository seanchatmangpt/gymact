from collections.abc import Iterable

from .errors import Refused

REQUIRED = frozenset({
    "DISCOVERY", "CONFORMANCE", "SIMULATION", "PREDICTION", "OPTIMIZATION",
    "INTERVENTION", "MONITORING", "EVENT_CENTRIC", "OBJECT_CENTRIC", "DECLARATIVE", "PROCEDURAL",
})


def require_methodologies(methodologies: Iterable[str]) -> frozenset[str]:
    admitted = frozenset(methodologies)
    missing = REQUIRED - admitted
    if missing:
        raise Refused("INCOMPLETE_METHODOLOGY_CLOSURE", ",".join(sorted(missing)))
    return admitted
