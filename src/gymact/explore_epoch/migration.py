from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class MigrationDisposition(str, Enum):
    REPLAY = "REPLAY"
    REQUALIFY = "REQUALIFY"
    BLOCK = "BLOCK"


@dataclass(frozen=True)
class MigrationDecision:
    consumer_key: str
    from_generation: int
    to_generation: int
    disposition: MigrationDisposition


def decide(consumer_key: str, from_generation: int, to_generation: int, schema_compatible: bool, producer_healthy: bool) -> MigrationDecision:
    if to_generation <= from_generation:
        raise ValueError("REFUSED_NON_FORWARD_EPOCH_MIGRATION")
    if not producer_healthy:
        disposition = MigrationDisposition.BLOCK
    elif schema_compatible:
        disposition = MigrationDisposition.REPLAY
    else:
        disposition = MigrationDisposition.REQUALIFY
    return MigrationDecision(consumer_key, from_generation, to_generation, disposition)
