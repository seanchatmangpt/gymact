from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .explore_ack_identity import Subject


class InvalidationReason(StrEnum):
    BUILD_BROKEN = "BUILD_BROKEN"
    SCHEMA_DRIFT = "SCHEMA_DRIFT"
    RECEIPT_SUPERSEDED = "RECEIPT_SUPERSEDED"
    LEASE_EXPIRED = "LEASE_EXPIRED"


@dataclass(frozen=True)
class Invalidation:
    event_id: str
    producer: Subject
    epoch: int
    reason: InvalidationReason

    def __post_init__(self) -> None:
        if not self.event_id.strip() or self.producer.role != "producer" or self.epoch < 1:
            raise ValueError("REFUSED_INVALID_INVALIDATION")
