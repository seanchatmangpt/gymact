from __future__ import annotations

from .calibration import CalibrationEvidence
from .errors import Refused
from .relation import Relation, maximal


def select_strongest(admitted: tuple[CalibrationEvidence, ...]) -> set[Relation]:
    if not admitted:
        raise Refused("NO_ADMITTED_RELATION")
    return maximal({e.relation for e in admitted})
