from __future__ import annotations

from dataclasses import dataclass

from .normalization import collapse_adjacent_duplicates
from .trace import Trace


@dataclass(frozen=True)
class StutterWitness:
    equivalent: bool
    left_length: int
    right_length: int
    normalized_length: int | None


def witness(left: Trace, right: Trace) -> StutterWitness:
    l = collapse_adjacent_duplicates(left)
    r = collapse_adjacent_duplicates(right)
    same = left.subject == right.subject and l.keys() == r.keys()
    return StutterWitness(same, len(left.events), len(right.events), len(l.events) if same else None)
