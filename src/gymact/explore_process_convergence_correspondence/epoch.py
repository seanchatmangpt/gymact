from dataclasses import dataclass
from datetime import datetime
from .errors import Refused
from .subject import SubjectEpoch
from .obligation import ObligationState

@dataclass(frozen=True)
class ClosureEpoch:
    subject: SubjectEpoch
    observed_at: datetime
    obligations: tuple[ObligationState, ...]

    def __post_init__(self) -> None:
        if self.observed_at.tzinfo is None:
            raise Refused("REFUSED_NAIVE_TIME")
        keys = [o.key for o in self.obligations]
        if len(keys) != len(set(keys)):
            raise Refused("REFUSED_DUPLICATE_OBLIGATION")
        object.__setattr__(self, "obligations", tuple(sorted(self.obligations, key=lambda o: o.key)))

    @property
    def universe(self) -> tuple[str, ...]:
        return tuple(o.key for o in self.obligations)
