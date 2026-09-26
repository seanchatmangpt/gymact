from __future__ import annotations

from gymact.enterprise_architecture import (
    ArchitectureWorld,
    SBBCandidate,
    method_frontier,
    qualified_frontier,
    select,
    transition,
)


def world() -> ArchitectureWorld:
    return ArchitectureWorld(
        strategy_digest="sha256:strategy-a",
        operating_model="coordination",
        abb_digest="sha256:abb",
        contract_digest="sha256:contract",
        baseline_sbb="sbb:baseline",
        candidates=(
            SBBCandidate(
                "sbb:a",
                "sha256:abb",
                "sha256:contract",
                "QUALIFIED",
                cost=10,
                risk=3,
                reversibility=8,
                method="reuse",
            ),
            SBBCandidate(
                "sbb:b",
                "sha256:abb",
                "sha256:contract",
                "QUALIFIED",
                cost=5,
                risk=7,
                reversibility=4,
                method="compose",
            ),
            SBBCandidate(
                "sbb:unknown",
                "sha256:abb",
                "sha256:contract",
                "UNKNOWN",
                cost=0,
                risk=0,
                reversibility=10,
                method="manufacture",
            ),
        ),
    )


def test_qualification_frontier_stays_plural_before_selection():
    frontier = qualified_frontier(world())
    assert [candidate.candidate_id for candidate in frontier] == ["sbb:a", "sbb:b"]


def test_strategy_pressure_can_change_selection_without_rewriting_abb_identity():
    cost_first = select(world(), cost_weight=10, risk_weight=1, reversibility_weight=1)
    reversible_first = select(world(), cost_weight=1, risk_weight=1, reversibility_weight=10)

    assert cost_first.abb_digest == reversible_first.abb_digest == "sha256:abb"
    assert cost_first.selected != reversible_first.selected
    assert cost_first.authority == "NONE"
    assert reversible_first.authority == "NONE"


def test_transition_reaches_target_or_rolls_back_on_supplier_failure():
    selected = select(world()).selected
    assert selected is not None

    success = transition(world(), selected)
    failure = transition(world(), selected, failure="SUPPLIER_OUTAGE")

    assert success.disposition == "TARGET_REACHED"
    assert success.target == selected
    assert failure.disposition == "ROLLED_BACK"
    assert failure.target == "sbb:baseline"
    assert failure.authority == "NONE"


def test_reuse_compose_extend_manufacture_remain_visible_as_distinct_methods():
    methods = method_frontier(world())
    assert methods["reuse"] == ("sbb:a",)
    assert methods["compose"] == ("sbb:b",)
    assert methods["manufacture"] == ()
