from __future__ import annotations

from dataclasses import dataclass

from .calibration import CalibrationEvidence
from .relation import Relation
from .selector_information import rank_information
from .selector_minimax import select_minimax
from .selector_pareto import frontier
from .selector_strongest import select_strongest


@dataclass(frozen=True)
class SelectionBundle:
    strongest: frozenset[Relation]
    minimax: tuple[Relation, ...]
    pareto: tuple[Relation, ...]
    information: tuple[Relation, ...]


def compare(admitted: tuple[CalibrationEvidence, ...]) -> SelectionBundle:
    return SelectionBundle(
        strongest=frozenset(select_strongest(admitted)),
        minimax=tuple(s.relation for s in select_minimax(admitted)),
        pareto=tuple(c.relation for c in frontier(admitted)),
        information=tuple(s.relation for s in rank_information(admitted)),
    )
