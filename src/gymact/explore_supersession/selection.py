from __future__ import annotations

from .candidates import Candidate
from .subject import Refusal


def pareto(candidates: tuple[Candidate, ...], scores: dict[str, tuple[int, ...]]) -> tuple[Candidate, ...]:
    survivors: list[Candidate] = []
    for candidate in candidates:
        own = scores[candidate.name]
        dominated = any(
            all(a >= b for a, b in zip(scores[other.name], own, strict=True))
            and any(a > b for a, b in zip(scores[other.name], own, strict=True))
            for other in candidates
            if other != candidate
        )
        if not dominated:
            survivors.append(candidate)
    return tuple(sorted(survivors, key=lambda item: item.name))


def weighted_select(candidates: tuple[Candidate, ...], scores: dict[str, tuple[int, ...]], weights: tuple[int, ...]) -> Candidate:
    if not candidates:
        raise Refusal("REFUSED_NO_VIABLE_CANDIDATE")
    ranked = sorted(
        candidates,
        key=lambda c: (sum(v * w for v, w in zip(scores[c.name], weights, strict=True)), c.name),
        reverse=True,
    )
    return ranked[0]
