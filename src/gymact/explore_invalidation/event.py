from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from .model import Refusal, Subject

KINDS = {"NEW_HEAD", "NEW_RECEIPT", "SCHEMA_CHANGE", "EXPIRED", "BUILD_BROKEN", "BLOCKED", "RECOVERED"}

@dataclass(frozen=True)
class InvalidationEvent:
    producer: Subject
    kind: str
    observed_at: datetime
    replacement_receipt: str | None = None
    def __post_init__(self) -> None:
        if self.kind not in KINDS or self.observed_at.tzinfo is None:
            raise Refusal("REFUSED_INVALID_INVALIDATION_EVENT")
        if self.kind == "NEW_RECEIPT" and not self.replacement_receipt:
            raise Refusal("REFUSED_MISSING_REPLACEMENT_RECEIPT")
