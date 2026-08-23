from __future__ import annotations

from enum import Enum


class Relation(str, Enum):
    EXACT = "EXACT"
    STUTTER = "STUTTER"
    ACTIVITY = "ACTIVITY"
    PARTIAL_ORDER = "PARTIAL_ORDER"


_DISCHARGES = {
    Relation.EXACT: frozenset({Relation.EXACT, Relation.STUTTER, Relation.ACTIVITY, Relation.PARTIAL_ORDER}),
    Relation.STUTTER: frozenset({Relation.STUTTER, Relation.ACTIVITY}),
    Relation.PARTIAL_ORDER: frozenset({Relation.PARTIAL_ORDER, Relation.ACTIVITY}),
    Relation.ACTIVITY: frozenset({Relation.ACTIVITY}),
}


def discharges(stronger: Relation, weaker: Relation) -> bool:
    return weaker in _DISCHARGES[stronger]


def maximal(relations: set[Relation]) -> set[Relation]:
    return {
        r for r in relations
        if not any(other != r and discharges(other, r) for other in relations)
    }
