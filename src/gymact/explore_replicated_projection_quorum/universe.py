from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from .refusal import Refused


@dataclass(frozen=True, slots=True)
class ReplicaUniverse:
    replica_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.replica_ids or len(set(self.replica_ids)) != len(self.replica_ids):
            raise Refused("REFUSED_INVALID_REPLICA_UNIVERSE")
        if any(not replica for replica in self.replica_ids):
            raise Refused("REFUSED_INVALID_REPLICA_UNIVERSE")

    @property
    def quorum_size(self) -> int:
        return len(self.replica_ids) // 2 + 1

    def coverage(self, observed_ids: set[str]) -> Fraction:
        return Fraction(len(observed_ids & set(self.replica_ids)), len(self.replica_ids))
