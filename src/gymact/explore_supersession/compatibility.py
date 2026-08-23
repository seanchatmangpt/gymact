from __future__ import annotations

from dataclasses import dataclass

from .frontier import Frontier


@dataclass(frozen=True)
class Compatibility:
    state: str
    reasons: tuple[str, ...]


def compare_frontiers(left: Frontier, right: Frontier) -> Compatibility:
    left_scopes = {(row.source, row.scope): row.outcome for row in left.current}
    right_scopes = {(row.source, row.scope): row.outcome for row in right.current}
    shared = sorted(set(left_scopes) & set(right_scopes))
    if not shared:
        return Compatibility("UNKNOWN", ("NO_SHARED_CURRENT_AXES",))
    diverged = tuple(
        f"{source}:{scope}"
        for source, scope in shared
        if left_scopes[(source, scope)] != right_scopes[(source, scope)]
    )
    if diverged:
        return Compatibility("DIVERGED", diverged)
    return Compatibility("COMPATIBLE", ())
