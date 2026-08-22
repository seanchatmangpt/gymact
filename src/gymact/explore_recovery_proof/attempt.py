from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone

from .context import RecoveryContext
from .subject import Refusal


@dataclass(frozen=True, slots=True)
class RecoveryAttempt:
    attempt_id: str
    ordinal: int
    base_fingerprint: str
    target_fingerprint: str
    strategy: str
    issued_at: datetime

    def __post_init__(self) -> None:
        if not self.attempt_id or self.ordinal < 0:
            raise Refusal("REFUSED_INVALID_RECOVERY_ATTEMPT")
        if len(self.base_fingerprint) != 64 or len(self.target_fingerprint) != 64:
            raise Refusal("REFUSED_INVALID_RECOVERY_ATTEMPT")
        if self.issued_at.tzinfo is None:
            raise Refusal("REFUSED_NAIVE_RECOVERY_TIME")

    @classmethod
    def issue(
        cls,
        attempt_id: str,
        ordinal: int,
        base: RecoveryContext,
        target: RecoveryContext,
        strategy: str,
        issued_at: datetime | None = None,
    ) -> RecoveryAttempt:
        return cls(
            attempt_id,
            ordinal,
            base.fingerprint,
            target.fingerprint,
            strategy,
            issued_at or datetime.now(timezone.utc),
        )

    @property
    def identity(self) -> str:
        payload = (
            f"{self.attempt_id}:{self.ordinal}:{self.base_fingerprint}:"
            f"{self.target_fingerprint}:{self.strategy}"
        )
        return hashlib.sha256(payload.encode()).hexdigest()
