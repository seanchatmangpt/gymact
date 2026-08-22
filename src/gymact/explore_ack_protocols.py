from __future__ import annotations
from dataclasses import dataclass
from enum import Enum

class ProtocolKind(str, Enum):
    ALL = "ALL"
    QUORUM = "QUORUM"
    CRITICAL_PATH = "CRITICAL_PATH"

@dataclass(frozen=True)
class Protocol:
    kind: ProtocolKind
    quorum: int = 0
    critical_consumers: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        if self.kind is ProtocolKind.QUORUM and self.quorum < 1:
            raise ValueError("REFUSED_INVALID_QUORUM")
        if self.kind is ProtocolKind.CRITICAL_PATH and not self.critical_consumers:
            raise ValueError("REFUSED_EMPTY_CRITICAL_PATH")

def candidates(total_consumers: int, critical: frozenset[str]) -> tuple[Protocol, ...]:
    if total_consumers < 1:
        raise ValueError("REFUSED_EMPTY_CONSUMER_SET")
    quorum = total_consumers // 2 + 1
    return (
        Protocol(ProtocolKind.ALL),
        Protocol(ProtocolKind.QUORUM, quorum=quorum),
        Protocol(ProtocolKind.CRITICAL_PATH, critical_consumers=critical),
    )
