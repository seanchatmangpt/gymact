import random
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class FailureWorld:
    seed: int
    family_probability: float
    flaky_probability: float

    def inject(
        self,
        rail_families: tuple[str, ...],
        rail_ids: tuple[str, ...],
    ) -> tuple[tuple[str, ...], tuple[str, ...]]:
        rng = random.Random(self.seed)
        failed_families = tuple(
            family
            for family in sorted(set(rail_families))
            if rng.random() < self.family_probability
        )
        flaky_rails = tuple(
            rail for rail in sorted(set(rail_ids)) if rng.random() < self.flaky_probability
        )
        return failed_families, flaky_rails
