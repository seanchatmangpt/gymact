from __future__ import annotations

from dataclasses import dataclass

@dataclass(frozen=True)
class Capability:
    semantic: str
    engine: str
    exact_arithmetic: bool
    bounded: bool


def discover() -> tuple[Capability, ...]:
    return (
        Capability("finite-w1-primal", "gymact.kantorovich.min_cost_flow/v1", True, True),
        Capability("finite-w1-oracle", "gymact.kantorovich.exhaustive/v1", True, True),
        Capability("independent-dual-verification", "gymact.kantorovich.independent/v1", True, True),
    )
