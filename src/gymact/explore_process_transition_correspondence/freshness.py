from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from .identity import Refused


@dataclass(frozen=True, slots=True)
class TimedEvidence:
    observed_at: datetime


def require_fresh(item: TimedEvidence, *, now: datetime, ttl: timedelta) -> TimedEvidence:
    if item.observed_at.tzinfo is None or now.tzinfo is None:
        raise Refused("REFUSED_NAIVE_TIME")
    observed = item.observed_at.astimezone(UTC)
    current = now.astimezone(UTC)
    if observed > current:
        raise Refused("REFUSED_FUTURE_EVIDENCE")
    if current - observed > ttl:
        raise Refused("REFUSED_STALE_EVIDENCE")
    return item
