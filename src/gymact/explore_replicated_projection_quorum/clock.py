from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .refusal import Refused


class ClockRelation(StrEnum):
    BEFORE = "BEFORE"
    AFTER = "AFTER"
    EQUAL = "EQUAL"
    CONCURRENT = "CONCURRENT"


@dataclass(frozen=True, slots=True)
class VectorClock:
    entries: tuple[tuple[str, int], ...]

    @classmethod
    def from_dict(cls, values: dict[str, int]) -> VectorClock:
        if not values:
            raise Refused("REFUSED_EMPTY_VECTOR_CLOCK")
        if any(not key or not isinstance(value, int) or value < 0 for key, value in values.items()):
            raise Refused("REFUSED_INVALID_VECTOR_CLOCK")
        return cls(tuple(sorted(values.items())))

    def as_dict(self) -> dict[str, int]:
        return dict(self.entries)

    def compare(self, other: VectorClock) -> ClockRelation:
        left, right = self.as_dict(), other.as_dict()
        keys = set(left) | set(right)
        le = all(left.get(k, 0) <= right.get(k, 0) for k in keys)
        ge = all(left.get(k, 0) >= right.get(k, 0) for k in keys)
        if le and ge:
            return ClockRelation.EQUAL
        if le:
            return ClockRelation.BEFORE
        if ge:
            return ClockRelation.AFTER
        return ClockRelation.CONCURRENT

    def join(self, other: VectorClock) -> VectorClock:
        left, right = self.as_dict(), other.as_dict()
        return VectorClock.from_dict(
            {key: max(left.get(key, 0), right.get(key, 0)) for key in set(left) | set(right)}
        )
