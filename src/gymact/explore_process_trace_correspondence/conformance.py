from __future__ import annotations

from dataclasses import dataclass

from .trace import Trace


@dataclass(frozen=True)
class Conformance:
    matched: int
    expected: int
    observed: int

    @property
    def precision(self) -> float:
        return self.matched / self.observed if self.observed else 0.0

    @property
    def recall(self) -> float:
        return self.matched / self.expected if self.expected else 0.0


def compare(expected: Trace, observed: Trace) -> Conformance:
    remaining = list(observed.keys())
    expected_keys = expected.keys()
    matched = 0
    for key in expected_keys:
        if key in remaining:
            matched += 1
            remaining.remove(key)
    return Conformance(matched, len(expected.events), len(observed.events))
