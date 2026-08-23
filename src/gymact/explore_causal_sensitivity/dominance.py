from enum import StrEnum

from .manski import Interval


class Relation(StrEnum):
    STRICTLY_BETTER = "STRICTLY_BETTER"
    STRICTLY_WORSE = "STRICTLY_WORSE"
    OVERLAP = "OVERLAP"


def compare(a: Interval, b: Interval) -> Relation:
    if a.lower > b.upper:
        return Relation.STRICTLY_BETTER
    if a.upper < b.lower:
        return Relation.STRICTLY_WORSE
    return Relation.OVERLAP
