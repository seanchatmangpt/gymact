from dataclasses import dataclass
import random

@dataclass(frozen=True)
class FailureWorld:
    seed: int
    dropped: tuple[str, ...]
    biased: tuple[str, ...]

def build_failure_world(sensors: list[str], seed: int) -> FailureWorld:
    rng = random.Random(seed)
    ordered = sorted(sensors)
    dropped = tuple(s for s in ordered if rng.random() < 0.2)
    biased = tuple(s for s in ordered if s not in dropped and rng.random() < 0.3)
    return FailureWorld(seed, dropped, biased)
