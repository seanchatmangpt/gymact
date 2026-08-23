from .refusal import Refused

REQUIRED = frozenset({"discovery","conformance","simulation","prediction","optimization","intervention","monitoring","event-centric","object-centric","declarative","procedural"})

def require_methodologies(observed: frozenset[str]) -> None:
    missing = REQUIRED - observed
    if missing:
        raise Refused("INCOMPLETE_METHODOLOGY_CLOSURE", ",".join(sorted(missing)))
