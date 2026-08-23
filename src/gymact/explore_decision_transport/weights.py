from fractions import Fraction

from .population import Population
from .refusal import Refused


def importance_weights(source: Population, target: Population, cap: Fraction | None = None) -> dict[str, Fraction]:
    out: dict[str, Fraction] = {}
    for key, target_mass in target.masses.items():
        source_mass = source.masses.get(key, Fraction())
        if target_mass > 0 and source_mass <= 0:
            raise Refused("POSITIVITY_VIOLATION", key)
        weight = target_mass / source_mass if source_mass else Fraction()
        out[key] = min(weight, cap) if cap is not None else weight
    return out


def effective_sample_size(weights: list[Fraction]) -> Fraction:
    if not weights:
        return Fraction()
    s1 = sum(weights, Fraction())
    s2 = sum((w * w for w in weights), Fraction())
    return Fraction() if s2 == 0 else s1 * s1 / s2
