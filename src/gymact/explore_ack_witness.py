from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from .explore_ack_identity import Subject

class WitnessKind(str, Enum):
    DELIVERED = "DELIVERED"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    DISCHARGED = "DISCHARGED"

@dataclass(frozen=True)
class Witness:
    event_id: str
    consumer: Subject
    kind: WitnessKind
    sequence: int
    digest: str = ""

    def __post_init__(self) -> None:
        if self.consumer.role != "consumer" or self.sequence < 1 or not self.event_id:
            raise ValueError("REFUSED_INVALID_WITNESS")
        if self.kind is WitnessKind.DISCHARGED and not self.digest:
            raise ValueError("REFUSED_DISCHARGE_WITHOUT_RECEIPT")
