from __future__ import annotations

from dataclasses import dataclass

@dataclass(frozen=True)
class Generation:
    generation: int
    semantic_digest: str


def current(values: list[Generation]) -> Generation:
    if not values:
        raise ValueError("REFUSED[EMPTY_CURRENTNESS_FRONTIER]")
    latest = max(v.generation for v in values)
    candidates = [v for v in values if v.generation == latest]
    if len({v.semantic_digest for v in candidates}) != 1:
        raise ValueError("REFUSED[DIVERGENT_CURRENT_SEMANTICS]")
    return candidates[0]
