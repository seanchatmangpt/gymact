from __future__ import annotations

import random
from dataclasses import replace

from .contracts import Refusal
from .witness import CurrentWitness


def inject_miscalibration(
    witnesses: tuple[CurrentWitness, ...], *, seed: int, probability_ppm: int
) -> tuple[CurrentWitness, ...]:
    if not 0 <= probability_ppm <= 1_000_000:
        raise Refusal("REFUSED_INVALID_FAILURE_PROBABILITY")
    rng = random.Random(seed)
    out: list[CurrentWitness] = []
    for witness in witnesses:
        should_flip = (
            witness.outcome in {"PASS", "FAIL"} and rng.randrange(1_000_000) < probability_ppm
        )
        if should_flip:
            outcome = "FAIL" if witness.outcome == "PASS" else "PASS"
            out.append(replace(witness, outcome=outcome))
        else:
            out.append(witness)
    return tuple(out)
