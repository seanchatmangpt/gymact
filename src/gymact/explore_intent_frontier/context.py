from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256
import json
import re
from .subject import Subject

_HEX64 = re.compile(r"^[0-9a-f]{64}$")

@dataclass(frozen=True, slots=True)
class SelectionContext:
    subject: Subject
    cut_id: str
    cut_digest: str
    cut_generation: int
    strategy: str
    policy_digest: str

    def __post_init__(self) -> None:
        if not self.cut_id or self.cut_generation < 0:
            raise ValueError("REFUSED_INVALID_SELECTION_CONTEXT")
        if not _HEX64.fullmatch(self.cut_digest) or not _HEX64.fullmatch(self.policy_digest):
            raise ValueError("REFUSED_INVALID_SELECTION_CONTEXT")
        if not self.strategy:
            raise ValueError("REFUSED_INVALID_SELECTION_CONTEXT")

    @property
    def fingerprint(self) -> str:
        body={"subject":self.subject.identity,"cut_id":self.cut_id,"cut_digest":self.cut_digest,
              "cut_generation":self.cut_generation,"strategy":self.strategy,
              "policy_digest":self.policy_digest}
        return sha256(json.dumps(body, sort_keys=True, separators=(",",":")).encode()).hexdigest()
