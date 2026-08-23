from .refusal import Refused

REQUIRED = frozenset(
    {
        "discovery",
        "conformance",
        "simulation",
        "prediction",
        "optimization",
        "intervention",
        "monitoring",
        "event-centric",
        "object-centric",
        "declarative",
        "procedural",
    }
)


def require_methodologies(observed: set[str]) -> None:
    missing = sorted(REQUIRED - observed)
    if missing:
        raise Refused("INCOMPLETE_METHODOLOGY_CLOSURE", ",".join(missing))
