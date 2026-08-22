from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from .subject import Refusal, Subject


@dataclass(frozen=True, slots=True)
class RecoveryContext:
    subject: Subject
    cut_id: str
    strategy: str
    policy_digest: str
    generation: int

    def __post_init__(self) -> None:
        if not self.cut_id or not self.strategy or len(self.policy_digest) != 64:
            raise Refusal("REFUSED_INVALID_RECOVERY_CONTEXT")
        if self.generation < 0:
            raise Refusal("REFUSED_INVALID_RECOVERY_GENERATION")
        try:
            int(self.policy_digest, 16)
        except ValueError as exc:
            raise Refusal("REFUSED_INVALID_RECOVERY_CONTEXT") from exc

    @property
    def fingerprint(self) -> str:
        body = {
            "subject": self.subject.identity,
            "cut_id": self.cut_id,
            "strategy": self.strategy,
            "policy_digest": self.policy_digest,
            "generation": self.generation,
        }
        payload = json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(payload).hexdigest()
