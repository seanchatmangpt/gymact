from dataclasses import dataclass
from enum import IntEnum
from fractions import Fraction
from .errors import Refused

class State(IntEnum):
    PASS = 0
    UNSUPPORTED = 1
    UNKNOWN = 2
    REFUSED = 3
    BLOCKED = 4
    FAIL = 5

@dataclass(frozen=True)
class ObligationState:
    key: str
    state: State
    weight: Fraction = Fraction(1)

    def __post_init__(self) -> None:
        if not self.key:
            raise Refused("REFUSED_EMPTY_OBLIGATION")
        if self.weight <= 0:
            raise Refused("REFUSED_NONPOSITIVE_WEIGHT")
