from __future__ import annotations

from fractions import Fraction
from typing import Any

from .measure import FiniteMeasure
from .refusal import Refused

def from_distribution(value: Any) -> FiniteMeasure:
    """Admit predecessor distribution objects without importing their implementation."""
    mass = getattr(value, "mass", None)
    if mass is None:
        raise Refused("UNSUPPORTED_DISTRIBUTION_ADAPTER")
    if isinstance(mass, dict):
        return FiniteMeasure.from_mapping(mass)
    try:
        return FiniteMeasure.from_mapping({str(k): Fraction(v) for k, v in mass})
    except (TypeError, ValueError, ZeroDivisionError) as exc:
        raise Refused("UNSUPPORTED_DISTRIBUTION_ADAPTER") from exc
