from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from .clock import ClockRelation
from .replica import ReplicaProjection


@dataclass(frozen=True, slots=True)
class CausalProfile:
    maximal_replica_ids: tuple[str, ...]
    concurrent_pairs: int
    total_pairs: int

    @property
    def concurrency_ratio(self) -> Fraction:
        if not self.total_pairs:
            return Fraction(0, 1)
        return Fraction(self.concurrent_pairs, self.total_pairs)


def causal_profile(observations: tuple[ReplicaProjection, ...]) -> CausalProfile:
    maxima: list[str] = []
    concurrent = 0
    total = 0
    for index, left in enumerate(observations):
        dominated = False
        for right in observations:
            if left is right:
                continue
            relation = left.clock.compare(right.clock)
            if relation is ClockRelation.BEFORE:
                dominated = True
        if not dominated:
            maxima.append(left.replica_id)
        for right in observations[index + 1 :]:
            total += 1
            if left.clock.compare(right.clock) is ClockRelation.CONCURRENT:
                concurrent += 1
    return CausalProfile(tuple(sorted(maxima)), concurrent, total)
