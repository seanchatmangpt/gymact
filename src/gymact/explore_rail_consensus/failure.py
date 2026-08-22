from dataclasses import dataclass
import random

@dataclass(frozen=True, slots=True)
class CorrelatedFailureWorld:
    seed: int
    probability: float

    def failed_families(self, families: tuple[str, ...]) -> tuple[str, ...]:
        rng = random.Random(self.seed)
        return tuple(sorted(family for family in sorted(set(families)) if rng.random() < self.probability))
