from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from .identity import Refused


@dataclass(frozen=True, slots=True)
class TimedEvidence:
    observed_at: datetime


def require_fresh(item: TimedEvidence, *, now: datetime, ttl: timedelta) -> TimedEvidence:
    if item.observed_at.tzinfo is None or now.tzinfo is None:
        raise Refused("REFUSED_NAIVE_TIME")
    observed = item.observed_at.astimezone(timezone.utc)
    current = now.astimezone(timezone.utc)
    if observed > current:
        raise Refused("REFUSED_FUTURE_EVIDENCE")
    if current - observed > ttl:
        raise Refused("REFUSED_STALE_EVIDENCE")
    return item
