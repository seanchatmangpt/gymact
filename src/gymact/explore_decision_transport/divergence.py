from fractions import Fraction

from .population import Population


def total_variation(source: Population, target: Population) -> Fraction:
    keys = set(source.masses) | set(target.masses)
    return sum(abs(source.masses.get(k, Fraction()) - target.masses.get(k, Fraction())) for k in keys) / 2
