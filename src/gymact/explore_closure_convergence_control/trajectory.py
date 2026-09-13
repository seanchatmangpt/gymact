from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from .refusal import Refused
from .state import Obligation
from .subject import SubjectEpoch


@dataclass(frozen=True, slots=True)
class ClosureEpoch:
    subject: SubjectEpoch
    observed_at: datetime
    obligations: tuple[Obligation, ...]

    def __post_init__(self) -> None:
        if self.observed_at.tzinfo is None:
            raise Refused("NAIVE_TIME", "closure epoch requires timezone")
        keys = [item.key for item in self.obligations]
        if not keys or len(keys) != len(set(keys)):
            raise Refused("INVALID_OBLIGATION_UNIVERSE", repr(keys))


def admit_trajectory(epochs: tuple[ClosureEpoch, ...]) -> tuple[ClosureEpoch, ...]:
    if len(epochs) < 2:
        raise Refused("INSUFFICIENT_TRAJECTORY", str(len(epochs)))
    universe = {item.key for item in epochs[0].obligations}
    for previous, current in zip(epochs, epochs[1:], strict=True):
        if current.subject.repo != previous.subject.repo:
            raise Refused("FOREIGN_SUBJECT", current.subject.repo)
        if current.subject.generation != previous.subject.generation + 1:
            raise Refused("TORN_GENERATION", current.subject.canonical)
        if current.observed_at <= previous.observed_at:
            raise Refused("NONMONOTONE_TIME", current.observed_at.isoformat())
        if {item.key for item in current.obligations} != universe:
            raise Refused("OBLIGATION_UNIVERSE_DRIFT", current.subject.canonical)
    return epochs


def now_utc() -> datetime:
    return datetime.now(timezone.utc)
