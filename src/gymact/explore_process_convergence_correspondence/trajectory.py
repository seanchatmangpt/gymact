from dataclasses import dataclass
from .epoch import ClosureEpoch
from .errors import Refused

@dataclass(frozen=True)
class Trajectory:
    epochs: tuple[ClosureEpoch, ...]

    def __post_init__(self) -> None:
        if len(self.epochs) < 2:
            raise Refused("REFUSED_TRAJECTORY_TOO_SHORT")
        universe = self.epochs[0].universe
        for a, b in zip(self.epochs, self.epochs[1:]):
            if b.subject.generation != a.subject.generation + 1:
                raise Refused("REFUSED_TORN_GENERATION")
            if b.observed_at <= a.observed_at:
                raise Refused("REFUSED_NONMONOTONE_TIME")
            if b.universe != universe:
                raise Refused("REFUSED_OBLIGATION_UNIVERSE_DRIFT")
