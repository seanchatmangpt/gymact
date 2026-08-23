from collections.abc import Iterable

from .selectors import Candidate


def dominates(left: Candidate, right: Candidate) -> bool:
    no_worse = (
        left.realized_risk <= right.realized_risk
        and left.false_independent_rate <= right.false_independent_rate
        and left.realized_information >= right.realized_information
        and left.drift_risk <= right.drift_risk
    )
    strictly = (
        left.realized_risk < right.realized_risk
        or left.false_independent_rate < right.false_independent_rate
        or left.realized_information > right.realized_information
        or left.drift_risk < right.drift_risk
    )
    return no_worse and strictly


def frontier(candidates: Iterable[Candidate]) -> tuple[Candidate, ...]:
    rows = tuple(candidates)
    return tuple(
        row for row in rows if not any(other != row and dominates(other, row) for other in rows)
    )
