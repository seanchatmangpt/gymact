from __future__ import annotations

from .errors import require

REQUIRED = frozenset(
    {
        "discovery",
        "conformance",
        "simulation",
        "prediction",
        "optimization",
        "intervention",
        "monitoring",
        "event_centric",
        "object_centric",
        "declarative",
        "procedural",
    }
)


def require_methodologies(observed: frozenset[str]) -> None:
    missing = REQUIRED - observed
    require(not missing, "INCOMPLETE_METHODOLOGY", ",".join(sorted(missing)))
