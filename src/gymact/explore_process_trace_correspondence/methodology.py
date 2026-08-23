from __future__ import annotations

from .refusal import Refused

REQUIRED = frozenset({
    "discovery", "conformance", "simulation", "prediction", "optimization",
    "intervention", "monitoring", "event_centric", "object_centric",
    "declarative", "procedural",
})


def require_complete(observed: frozenset[str]) -> None:
    missing = REQUIRED - observed
    extra = observed - REQUIRED
    if extra:
        raise Refused("UNKNOWN_METHODOLOGY", ",".join(sorted(extra)))
    if missing:
        raise Refused("INCOMPLETE_METHODOLOGY_TRACE_COVERAGE", ",".join(sorted(missing)))
