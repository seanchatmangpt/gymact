from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from .perturbation import Perturbation


@dataclass(frozen=True, slots=True)
class StressWorld:
    name: str
    perturbations: tuple[Perturbation, ...]


def support_erosion(cell: str, amount: Fraction) -> StressWorld:
    return StressWorld("support_erosion", (Perturbation(cell, source_delta=-amount),))


def target_shift(cell: str, amount: Fraction) -> StressWorld:
    return StressWorld("target_shift", (Perturbation(cell, target_delta=amount),))
