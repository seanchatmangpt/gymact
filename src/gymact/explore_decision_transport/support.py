from fractions import Fraction

from .population import Population
from .refusal import Refused


def support_overlap(source: Population, target: Population) -> Fraction:
    missing = [
        k
        for k, mass in target.masses.items()
        if mass > 0 and source.masses.get(k, Fraction()) <= 0
    ]
    if missing:
        raise Refused("POSITIVITY_VIOLATION", ",".join(missing))
    return sum(min(source.masses.get(k, Fraction()), v) for k, v in target.masses.items())
