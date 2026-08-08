from __future__ import annotations

from gymact.combinatorial import Combination, ObjectiveVector
from gymact.models import Standing
from gymact.possibility_index import EmpiricalCombinationRecord, EmpiricalPossibilityIndex


def record(
    planner: str,
    *,
    cost: float,
    latency: float,
    standing: Standing = Standing.ALIVE,
) -> EmpiricalCombinationRecord:
    return EmpiricalCombinationRecord(
        problem_class_ref="urn:problem:class",
        structural_key="structure-1",
        combination=Combination(assignments={"planner": planner, "provider": "e1"}),
        observed=ObjectiveVector(
            monetary_cost=cost,
            wall_time_s=latency,
            expected_value=1.0,
        ),
        standing=standing,
        receipt_refs=(f"urn:receipt:{planner}",),
    )


def test_inapplicable_record_cannot_win_ranking() -> None:
    index = EmpiricalPossibilityIndex()
    fast_but_inapplicable = record("p-fast", cost=0.1, latency=0.1)
    cheap = record("p-cheap", cost=1.0, latency=5.0)
    fast = record("p-latency", cost=5.0, latency=1.0)
    for value in (fast_but_inapplicable, cheap, fast):
        index.record(value)

    eligible = (cheap.combination.combination_id, fast.combination.combination_id)
    frontier = index.query(
        problem_class_ref="urn:problem:class",
        structural_key="structure-1",
        eligible_combination_ids=eligible,
    )
    assert {item.combination.assignments["planner"] for item in frontier} == {
        "p-cheap",
        "p-latency",
    }
    assert all(item.combination != fast_but_inapplicable.combination for item in frontier)


def test_empty_applicability_set_produces_no_ranking() -> None:
    index = EmpiricalPossibilityIndex()
    index.record(record("p1", cost=1.0, latency=1.0))
    assert (
        index.query(
            problem_class_ref="urn:problem:class",
            structural_key="structure-1",
            eligible_combination_ids=(),
        )
        == ()
    )


def test_failed_empirical_record_is_evidence_but_not_a_ranked_candidate() -> None:
    index = EmpiricalPossibilityIndex()
    failed = record("failed", cost=0.0, latency=0.0, standing=Standing.REFUSED)
    alive = record("alive", cost=2.0, latency=2.0)
    index.record(failed)
    index.record(alive)
    frontier = index.query(
        problem_class_ref="urn:problem:class",
        structural_key="structure-1",
        eligible_combination_ids=(
            failed.combination.combination_id,
            alive.combination.combination_id,
        ),
    )
    assert tuple(item.combination.assignments["planner"] for item in frontier) == ("alive",)
