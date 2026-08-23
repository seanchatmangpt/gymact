from dataclasses import dataclass

from .errors import Refused

@dataclass(frozen=True, slots=True)
class ObservationPropensity:
    decision_id: str
    probability: float
    mechanism_digest: str

    def __post_init__(self) -> None:
        if not self.decision_id or not 0.0 < self.probability <= 1.0:
            raise Refused("POSITIVITY_VIOLATION")
        if len(self.mechanism_digest) != 64 or any(c not in "0123456789abcdef" for c in self.mechanism_digest):
            raise Refused("INVALID_OBSERVATION_MECHANISM")

    @property
    def weight(self) -> float:
        return 1.0 / self.probability
