from __future__ import annotations

from enum import StrEnum

from .normalization import collapse_adjacent_duplicates, project_activities
from .refusal import Refused
from .trace import Trace


class Equivalence(StrEnum):
    EXACT = "exact"
    ACTIVITY = "activity"
    STUTTER = "stutter"


def equivalent(left: Trace, right: Trace, relation: Equivalence) -> bool:
    if left.subject != right.subject:
        raise Refused("FOREIGN_SUBJECT_TRACE")
    if relation is Equivalence.EXACT:
        return left.keys() == right.keys()
    if relation is Equivalence.ACTIVITY:
        return project_activities(left) == project_activities(right)
    if relation is Equivalence.STUTTER:
        left_normal = collapse_adjacent_duplicates(left)
        right_normal = collapse_adjacent_duplicates(right)
        return left_normal.keys() == right_normal.keys()
    raise Refused("UNKNOWN_EQUIVALENCE", str(relation))
