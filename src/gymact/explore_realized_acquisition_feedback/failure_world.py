import random
from dataclasses import dataclass


@dataclass(frozen=True)
class FailureWorld:
    seed: int
    dropped: tuple[str, ...]
    biased: tuple[str, ...]


def build_failure_world(sensors: list[str], seed: int) -> FailureWorld:
    rng = random.Random(seed)
    ordered = sorted(sensors)
    dropped = tuple(sensor for sensor in ordered if rng.random() < 0.2)
    biased = tuple(
        sensor for sensor in ordered if sensor not in dropped and rng.random() < 0.3
    )
    return FailureWorld(seed, dropped, biased)
