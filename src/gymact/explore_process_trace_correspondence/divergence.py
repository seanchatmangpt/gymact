from __future__ import annotations

from dataclasses import dataclass
from itertools import zip_longest

from .trace import Trace


@dataclass(frozen=True)
class Divergence:
    index: int
    left: tuple[str, str, str] | None
    right: tuple[str, str, str] | None


def first_divergence(left: Trace, right: Trace) -> Divergence | None:
    if left.subject != right.subject:
        return Divergence(-1, None, None)
    for index, (a, b) in enumerate(zip_longest(left.keys(), right.keys())):
        if a != b:
            return Divergence(index, a, b)
    return None
