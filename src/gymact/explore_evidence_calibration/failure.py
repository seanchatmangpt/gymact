from __future__ import annotations
from dataclasses import replace
import random
from .witness import CurrentWitness

def inject_miscalibration(witnesses: tuple[CurrentWitness, ...], *, seed: int, probability_ppm: int) -> tuple[CurrentWitness, ...]:
    if not 0 <= probability_ppm <= 1_000_000: raise ValueError("REFUSED_INVALID_FAILURE_PROBABILITY")
    rng=random.Random(seed); out=[]
    for witness in witnesses:
        if witness.outcome in {"PASS","FAIL"} and rng.randrange(1_000_000)<probability_ppm:
            out.append(replace(witness,outcome="FAIL" if witness.outcome=="PASS" else "PASS"))
        else: out.append(witness)
    return tuple(out)
