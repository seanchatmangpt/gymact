from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ObligationState(StrEnum):
    UNKNOWN = "UNKNOWN"
    PASS = "PASS"
    FAIL = "FAIL"
    REFUSED = "REFUSED"


@dataclass(frozen=True, slots=True)
class Obligation:
    key: str
    state: ObligationState
    source_id: str

    def __post_init__(self) -> None:
        if not self.key or not self.source_id:
            raise ValueError("REFUSED_EMPTY_OBLIGATION_IDENTITY")
