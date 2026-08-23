from datetime import UTC, datetime, timedelta

import pytest

from gymact.explore_reconciliation import (
    Candidate,
    ObservationWindow,
    Subject,
    ahp_priority,
    diff,
    discover,
    full_factorial,
    pareto_frontier,
    qualify,
    reachable,
    replay,
    require_explore_authority,
    weighted_pugh,
)
from gymact.explore_reconciliation.observation import Observation
from gymact.explore_reconciliation.receipt import Receipt

SHA = "7" * 40
NOW = datetime(2026, 8, 22, 9, 0, tzinfo=UTC)
SUBJECT = Subject("seanchatmangpt/gymact", SHA, "explore/test")
WINDOW = ObservationWindow(NOW - timedelta(hours=2), NOW + timedelta(seconds=1))


def obs(axis: str, outcome: str = "PASS", source: str = "github") -> Observation:
    return Observation(SUBJECT, axis, outcome, NOW, source)


def test_exact_subject_refuses_short_sha() -> None:
    with pytest.raises(ValueError, match="REFUSED_INEXACT_SUBJECT_SHA"):
        Subject("seanchatmangpt/gymact", "abc")


def test_window_is_half_open_and_timezone_aware() -> None:
    assert WINDOW.contains(NOW)
    assert not WINDOW.contains(WINDOW.end)


def test_foreign_subject_refuses_at_admission() -> None:
    foreign = Subject("seanchatmangpt/gymact", "8" * 40)
    with pytest.raises(ValueError, match="REFUSED_FOREIGN_SUBJECT_OBSERVATION"):
        qualify(SUBJECT, WINDOW, (Observation(foreign, "ci", "PASS", NOW, "github"),))


def test_contradictory_source_refuses() -> None:
    with pytest.raises(ValueError, match="REFUSED_CONTRADICTORY_OBSERVATION"):
        qualify(SUBJECT, WINDOW, (obs("ci"), obs("ci", "FAIL")))


def test_failure_dominates_bounded_standing() -> None:
    result = qualify(SUBJECT, WINDOW, (obs("focused"), obs("repository", "FAIL", "matrix")))
    assert result.standing == "BUILD_BROKEN"
    assert result.actuation_performed is False


def test_all_pass_caps_at_partial_alive() -> None:
    result = qualify(SUBJECT, WINDOW, (obs("focused"), obs("world", source="crown")))
    assert result.standing == "PARTIAL_ALIVE"


def test_receipt_replay_detects_tamper() -> None:
    result = qualify(SUBJECT, WINDOW, (obs("focused"),))
    assert replay(result.receipt, SUBJECT, result.observations)
    tampered = Receipt(
        result.receipt.subject,
        result.receipt.standing,
        result.receipt.evidence,
        False,
        "0" * 64,
    )
    with pytest.raises(ValueError, match="REFUSED_RECEIPT_REPLAY_MISMATCH"):
        replay(tampered, SUBJECT, result.observations)


def test_direct_do_is_refused() -> None:
    with pytest.raises(ValueError, match="REFUSED_UNRECEIPTED_ACTUATION"):
        require_explore_authority("DO")


def test_capability_discovery_preserves_multiple_candidates() -> None:
    candidates = (
        Candidate("memory", frozenset({"store", "replay"}), True, 1, 0.1),
        Candidate("jsonl", frozenset({"store", "replay"}), True, 2, 0.05),
    )
    assert {c.candidate_id for c in discover(candidates, {"replay"})} == {"memory", "jsonl"}


def test_pareto_keeps_non_dominated_tradeoffs() -> None:
    candidates = (
        Candidate("cheap", frozenset({"x"}), True, 1, 0.4),
        Candidate("safe", frozenset({"x"}), True, 2, 0.1),
        Candidate("dominated", frozenset({"x"}), True, 3, 0.5),
    )
    assert {c.candidate_id for c in pareto_frontier(candidates)} == {"cheap", "safe"}


def test_pugh_and_ahp_are_deterministic() -> None:
    ranked = weighted_pugh({"a": {"x": 1, "y": 0}, "b": {"x": 0, "y": 1}}, {"x": 2, "y": 1})
    assert ranked[0][0] == "a"
    priorities = ahp_priority(((1.0, 2.0), (0.5, 1.0)))
    assert priorities[0] > priorities[1]


def test_full_factorial_preserves_all_reversible_combinations() -> None:
    rows = full_factorial({"runtime": ("python", "wasm"), "store": ("memory", "jsonl")})
    assert len(rows) == 4


def test_differential_reports_exact_path() -> None:
    assert diff({"a": {"b": 1}}, {"a": {"b": 2}}) == ("$.a.b",)


def test_graph_failure_does_not_imply_graph_failure() -> None:
    edges = (("observe", "select"), ("observe", "fallback"), ("fallback", "select"))
    assert reachable(edges, "observe", "select")
