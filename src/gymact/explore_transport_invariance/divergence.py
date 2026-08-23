from __future__ import annotations

from fractions import Fraction

from .population import Cell


def total_variation(cells: tuple[Cell, ...]) -> Fraction:
    return sum((abs(c.source_mass - c.target_mass) for c in cells), Fraction()) / 2


def overlap_coefficient(cells: tuple[Cell, ...]) -> Fraction:
    return sum((min(c.source_mass, c.target_mass) for c in cells), Fraction())
