from __future__ import annotations

from fractions import Fraction

from .potential import DualPotential


def normalize_gauge(potential: DualPotential) -> DualPotential:
    anchor = min(potential.u) if potential.u else None
    shift = potential.u[anchor] if anchor is not None else Fraction(0)
    return DualPotential(
        {k: v - shift for k, v in potential.u.items()},
        {k: v + shift for k, v in potential.v.items()},
    )
