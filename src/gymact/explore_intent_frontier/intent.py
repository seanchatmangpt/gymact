from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

from .context import SelectionContext

_NONCE = re.compile(r"^[A-Za-z0-9_.:-]{8,128}$")


@dataclass(frozen=True, slots=True)
class SelectionIntent:
    context: SelectionContext
    nonce: str
    issued_at: datetime
    expires_at: datetime

    def __post_init__(self) -> None:
        if not _NONCE.fullmatch(self.nonce):
            raise ValueError("REFUSED_INVALID_INTENT_NONCE")
        if self.issued_at.tzinfo is None or self.expires_at.tzinfo is None:
            raise ValueError("REFUSED_NAIVE_INTENT_LEASE")
        if self.expires_at <= self.issued_at:
            raise ValueError("REFUSED_INVALID_INTENT_LEASE")

    def active(self, now: datetime) -> bool:
        if now.tzinfo is None:
            raise ValueError("REFUSED_NAIVE_OBSERVATION_TIME")
        return self.issued_at <= now < self.expires_at
