from __future__ import annotations

from collections import defaultdict

from .calibration import CalibrationEvidence
from .errors import Refused
from .relation import Relation


def current_frontier(
    evidence: tuple[CalibrationEvidence, ...],
) -> dict[Relation, CalibrationEvidence]:
    grouped: dict[Relation, list[CalibrationEvidence]] = defaultdict(list)
    for item in evidence:
        grouped[item.relation].append(item)
    out: dict[Relation, CalibrationEvidence] = {}
    for relation, items in grouped.items():
        generation = max(i.generation for i in items)
        newest = [i for i in items if i.generation == generation]
        if len(newest) != 1:
            raise Refused("DIVERGENT_CALIBRATION_FRONTIER", relation.value)
        out[relation] = newest[0]
    return out
