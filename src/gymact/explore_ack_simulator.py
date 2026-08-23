from __future__ import annotations

import random
from dataclasses import dataclass

from .explore_ack_identity import Subject
from .explore_ack_witness import Witness, WitnessKind


@dataclass(frozen=True)
class FailurePlan:
    seed: int
    drop_probability: float
    max_retries: int

    def __post_init__(self) -> None:
        if not 0 <= self.drop_probability <= 1 or self.max_retries < 0:
            raise ValueError("REFUSED_INVALID_FAILURE_PLAN")


def simulate(
    event_id: str,
    consumers: tuple[Subject, ...],
    plan: FailurePlan,
) -> tuple[Witness, ...]:
    rng = random.Random(plan.seed)
    output: list[Witness] = []
    for consumer in sorted(consumers, key=lambda c: c.key):
        sequence = 1
        for kind in (
            WitnessKind.DELIVERED,
            WitnessKind.ACKNOWLEDGED,
            WitnessKind.DISCHARGED,
        ):
            admitted = False
            for _ in range(plan.max_retries + 1):
                if rng.random() >= plan.drop_probability:
                    digest = (
                        f"{event_id}:{consumer.sha}:{sequence}"
                        if kind is WitnessKind.DISCHARGED
                        else ""
                    )
                    output.append(Witness(event_id, consumer, kind, sequence, digest))
                    admitted = True
                    break
            if not admitted:
                break
            sequence += 1
    return tuple(output)
