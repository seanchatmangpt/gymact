from __future__ import annotations

from dataclasses import dataclass

from .identity import Refused
from .obligation import ObligationState


@dataclass(frozen=True, slots=True)
class Discharge:
    obligation: str
    previous: ObligationState
    current: ObligationState
    proof_source_id: str

    def __post_init__(self) -> None:
        if self.previous is ObligationState.PASS or self.current is not ObligationState.PASS:
            raise Refused("REFUSED_NOT_A_DISCHARGE")
        if not self.proof_source_id:
            raise Refused("REFUSED_MISSING_DISCHARGE_PROOF")
