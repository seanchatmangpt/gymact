from __future__ import annotations

import random
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ScheduleStep:
    index: int
    actor: str
    operation: str


def deterministic_interleaving(
    seed: int, actors: tuple[str, ...], rounds: int = 2
) -> tuple[ScheduleStep, ...]:
    rng = random.Random(seed)
    operations = [
        (actor, operation)
        for _ in range(rounds)
        for actor in actors
        for operation in ("READ", "VALIDATE")
    ]
    rng.shuffle(operations)
    return tuple(
        ScheduleStep(index, actor, operation)
        for index, (actor, operation) in enumerate(operations)
    )


def aba_detected(observed: tuple[str, ...]) -> bool:
    return (
        len(observed) >= 3
        and observed[0] == observed[-1]
        and any(value != observed[0] for value in observed[1:-1])
    )
