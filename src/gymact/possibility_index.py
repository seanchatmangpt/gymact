"""Receipt-backed empirical index over admitted combinatorial possibilities."""
from __future__ import annotations

from typing import Iterable

from pydantic import Field

from gymact.combinatorial import Combination, ObjectiveVector
from gymact.models import FrozenModel, Standing


class EmpiricalCombinationRecord(FrozenModel):
    problem_class_ref: str = Field(min_length=1)
    structural_key: str = Field(min_length=1)
    combination: Combination
    objective: str = Field(default="verified_consequence", min_length=1)
    environment: str = Field(default="unspecified", min_length=1)
    hardware: str = Field(default="unspecified", min_length=1)
    observed: ObjectiveVector
    standing: Standing
    receipt_refs: tuple[str, ...] = Field(min_length=1)


def _dominates(left: EmpiricalCombinationRecord, right: EmpiricalCombinationRecord) -> bool:
    l = left.observed
    r = right.observed
    no_worse = (
        l.monetary_cost <= r.monetary_cost
        and l.wall_time_s <= r.wall_time_s
        and l.compute_units <= r.compute_units
        and l.human_interventions <= r.human_interventions
        and l.risk_score <= r.risk_score
        and l.verification_confidence >= r.verification_confidence
        and l.expected_value >= r.expected_value
    )
    better = (
        l.monetary_cost < r.monetary_cost
        or l.wall_time_s < r.wall_time_s
        or l.compute_units < r.compute_units
        or l.human_interventions < r.human_interventions
        or l.risk_score < r.risk_score
        or l.verification_confidence > r.verification_confidence
        or l.expected_value > r.expected_value
    )
    return no_worse and better


def empirical_pareto(
    records: Iterable[EmpiricalCombinationRecord],
) -> tuple[EmpiricalCombinationRecord, ...]:
    values = tuple(records)
    return tuple(
        candidate
        for candidate in values
        if not any(other is not candidate and _dominates(other, candidate) for other in values)
    )


class EmpiricalPossibilityIndex:
    """Retrieval index that cannot rank combinations absent from current applicability."""

    def __init__(self) -> None:
        self._records: list[EmpiricalCombinationRecord] = []

    def record(self, value: EmpiricalCombinationRecord) -> None:
        self._records.append(value)

    def query(
        self,
        *,
        problem_class_ref: str,
        structural_key: str,
        eligible_combination_ids: tuple[str, ...],
        objective: str = "verified_consequence",
        environment: str | None = None,
        hardware: str | None = None,
    ) -> tuple[EmpiricalCombinationRecord, ...]:
        """Filter by current lawful applicability before any Pareto comparison."""
        eligible = set(eligible_combination_ids)
        if not eligible:
            return ()
        records = (
            item
            for item in self._records
            if item.problem_class_ref == problem_class_ref
            and item.structural_key == structural_key
            and item.objective == objective
            and item.combination.combination_id in eligible
            and item.standing in {Standing.ALIVE, Standing.ADOPTED}
            and (environment is None or item.environment == environment)
            and (hardware is None or item.hardware == hardware)
        )
        return empirical_pareto(records)
