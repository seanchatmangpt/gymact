from __future__ import annotations

import pytest

from gymact.combinatorial import Combination, ObjectiveVector
from gymact.evidence import MemoryReceiptLedger
from gymact.models import Operation, Receipt, Standing
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
        receipt_refs=(f"urn:gymact:receipt:{planner}",),
    )


def ledger_for(*records: EmpiricalCombinationRecord) -> MemoryReceiptLedger:
    ledger = MemoryReceiptLedger()
    for value in records:
        planner = value.combination.assignments["planner"]
        ledger.append(
            Receipt(
                receipt_id=planner,
                episode_id=f"episode-{planner}",
                operation=Operation.VERIFY,
                standing=value.standing,
                verified=value.standing is Standing.ALIVE,
            )
        )
    return ledger


def test_inapplicable_record_cannot_win_ranking() -> None:
    fast_but_inapplicable = record("p-fast", cost=0.1, latency=0.1)
    cheap = record("p-cheap", cost=1.0, latency=5.0)
    fast = record("p-latency", cost=5.0, latency=1.0)
    values = (fast_but_inapplicable, cheap, fast)
    index = EmpiricalPossibilityIndex(ledger_for(*values))
    for value in values:
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
    value = record("p1", cost=1.0, latency=1.0)
    index = EmpiricalPossibilityIndex(ledger_for(value))
    index.record(value)
    assert (
        index.query(
            problem_class_ref="urn:problem:class",
            structural_key="structure-1",
            eligible_combination_ids=(),
        )
        == ()
    )


def test_failed_empirical_record_is_evidence_but_not_a_ranked_candidate() -> None:
    failed = record("failed", cost=0.0, latency=0.0, standing=Standing.REFUSED)
    alive = record("alive", cost=2.0, latency=2.0)
    index = EmpiricalPossibilityIndex(ledger_for(failed, alive))
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


def test_unresolved_receipt_cannot_seed_empirical_index() -> None:
    value = record("unwitnessed", cost=0.1, latency=0.1)
    index = EmpiricalPossibilityIndex(MemoryReceiptLedger())
    with pytest.raises(ValueError, match="EMPIRICAL_INDEX_RECEIPT_MISSING"):
        index.record(value)


def test_unverified_alive_receipt_cannot_seed_empirical_index() -> None:
    value = record("not-verified", cost=0.1, latency=0.1)
    ledger = MemoryReceiptLedger()
    ledger.append(
        Receipt(
            receipt_id="not-verified",
            episode_id="episode",
            operation=Operation.ACT,
            standing=Standing.ALIVE,
            verified=False,
        )
    )
    index = EmpiricalPossibilityIndex(ledger)
    with pytest.raises(ValueError, match="EMPIRICAL_INDEX_VERIFIED_CONSEQUENCE_REQUIRED"):
        index.record(value)
