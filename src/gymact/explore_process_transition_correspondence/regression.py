from __future__ import annotations

from dataclasses import dataclass

from .identity import Refused
from .obligation import ObligationState


@dataclass(frozen=True, slots=True)
class Regression:
    obligation: str
    previous: ObligationState
    current: ObligationState

    def __post_init__(self) -> None:
        if self.previous is not ObligationState.PASS or self.current is ObligationState.PASS:
            raise Refused("REFUSED_NOT_A_REGRESSION")

    @property
    def severity(self) -> int:
        return 2 if self.current is ObligationState.FAIL else 1
