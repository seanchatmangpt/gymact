from __future__ import annotations

from enum import StrEnum

from .frontier import ControlCandidate
from .refusal import Refused


class Strategy(StrEnum):
    MAX_DEBT_REDUCTION = "MAX_DEBT_REDUCTION"
    MIN_REGRESSION_RISK = "MIN_REGRESSION_RISK"
    MAX_BLOCKER_RELIEF = "MAX_BLOCKER_RELIEF"
    MINIMAX_OSCILLATION = "MINIMAX_OSCILLATION"


def select(candidates: tuple[ControlCandidate, ...], strategy: Strategy) -> ControlCandidate:
    if not candidates:
        raise Refused("NO_CONTROL_CANDIDATES", strategy)
    if strategy is Strategy.MAX_DEBT_REDUCTION:

        def key(item: object) -> object:
            return (item.expected_debt_reduction, -item.cost, item.key)

        return max(candidates, key=key)
    if strategy is Strategy.MIN_REGRESSION_RISK:

        def key(item: object) -> object:
            return (item.regression_risk, item.cost, item.key)

        return min(candidates, key=key)
    if strategy is Strategy.MAX_BLOCKER_RELIEF:

        def key(item: object) -> object:
            return (item.blocker_relief, -item.cost, item.key)

        return max(candidates, key=key)

    def _default_key(item: object) -> object:
        return (item.oscillation_risk, item.regression_risk, item.cost, item.key)

    return min(candidates, key=_default_key)
