from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from .subject import Refusal


@dataclass(frozen=True, order=True)
class Epoch:
    observed_at: datetime
    sequence: int = 0

    def __post_init__(self) -> None:
        if self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise Refusal("REFUSED_NAIVE_EPOCH")
        if self.sequence < 0:
            raise Refusal("REFUSED_NEGATIVE_EPOCH_SEQUENCE")

    def canonical(self) -> tuple[str, int]:
        instant = self.observed_at.astimezone(timezone.utc).isoformat()
        return instant, self.sequence
