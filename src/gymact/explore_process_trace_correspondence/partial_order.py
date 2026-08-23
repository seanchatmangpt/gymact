from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations

from .trace import Trace


@dataclass(frozen=True)
class PartialOrderSignature:
    precedence: frozenset[tuple[str, str]]


def signature(trace: Trace) -> PartialOrderSignature:
    activities = [event.activity for event in trace.events]
    pairs = {(activities[i], activities[j]) for i, j in combinations(range(len(activities)), 2) if activities[i] != activities[j]}
    return PartialOrderSignature(frozenset(pairs))


def equivalent(left: Trace, right: Trace) -> bool:
    return left.subject == right.subject and signature(left) == signature(right)
