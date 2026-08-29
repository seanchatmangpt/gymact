from __future__ import annotations

from itertools import combinations


def minimal_cut_sets(requirements: dict[str, frozenset[str]], failed: frozenset[str]) -> tuple[frozenset[str], ...]:
    """Return minimal failed-evidence sets that intersect every requirement alternative."""
    universe = sorted(failed)
    cuts: list[frozenset[str]] = []
    groups = tuple(requirements.values())
    for size in range(1, len(universe) + 1):
        for combo in combinations(universe, size):
            candidate = frozenset(combo)
            if groups and all(candidate & group for group in groups):
                if not any(existing < candidate for existing in cuts):
                    cuts.append(candidate)
    return tuple(cuts)
