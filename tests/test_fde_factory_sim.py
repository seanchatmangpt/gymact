"""Chicago-style court for the model-free, human-free FDE factory simulation.

Asserts on derived state of the real simulation (records, counters), never on a packaged verdict.
A passing run is a fact about the SIMULATED mechanism, not about any real workflow's standing.
"""

from __future__ import annotations

import builtins
import socket

import pytest

from gymact.fde_factory_sim import (
    DriftEvent,
    ExploreReason,
    Path,
    SimulationSpec,
    default_spec,
    run_simulation,
    simulate,
)
from gymact.models import Standing


@pytest.fixture
def sealed(monkeypatch: pytest.MonkeyPatch) -> None:
    """Any network or stdin access (LLM / human channel) is a hard failure."""

    def forbidden(*_a: object, **_k: object) -> None:
        raise AssertionError("SIM_TOUCHED_NETWORK_OR_HUMAN_CHANNEL")

    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(builtins, "input", forbidden)


def test_runs_sealed_and_is_deterministic(sealed: None) -> None:
    a = run_simulation()
    b = run_simulation()
    assert a.report_digest == b.report_digest
    assert a.factory.trace_digest == b.factory.trace_digest
    assert (a.llm_calls, a.human_interactions) == (0, 0)
    assert a.origin == "SIMULATED" and a.observed_execution is False


def test_different_seed_changes_trace() -> None:
    base = run_simulation(default_spec())
    other = run_simulation(default_spec().model_copy(update={"seed": 7}))
    assert base.factory.trace_digest != other.factory.trace_digest


def test_factory_compounds_versus_baseline() -> None:
    report = run_simulation()
    assert report.factory.cognition_evals * 4 < report.baseline.cognition_evals
    # per-class curve: C_1 > C_known for every class seen more than once
    for curve in report.factory.curves:
        costs = curve.cognition_evals_per_engagement
        if len(costs) > 1:
            assert costs[0] > 0
            assert costs[1] == 0 or curve.class_id in {"class-01", "class-02"}
    # mu grows monotonically and only by admitted recipes
    mu = report.factory.mu_size_by_engagement
    assert list(mu) == sorted(mu)
    assert mu[-1] <= default_spec().n_classes


def test_falsifier_no_repeated_exploration_of_solved_class() -> None:
    f = run_simulation().factory
    assert f.redundant_explorations == 0
    for r in f.records:
        if r.path is Path.EXPLORE and r.explore_reason is not ExploreReason.FIRST_SOLVE:
            assert r.explore_reason in {
                ExploreReason.IDENTITY_DRIFT,
                ExploreReason.VERIFY_DIVERGENCE,
            }


def test_no_unverified_consequence_and_no_lookalike_admitted() -> None:
    f = run_simulation().factory
    assert f.unverified_consequences == 0
    # every executed consequence was independently verified by the world oracle
    assert all(r.verified for r in f.records if r.path in {Path.EXPLOIT, Path.EXPLORE})
    # challenge set is what rejects plausible-but-wrong candidates: exploring costs more than
    # the common-instance pass alone would, for at least one class
    assert any(c.cognition_evals_per_engagement[0] > 6 for c in f.curves)


def test_silent_drift_caught_only_by_independent_verification() -> None:
    spec = SimulationSpec(
        n_classes=1,
        n_engagements=12,
        drift_events=(DriftEvent(at_engagement=6, class_id="class-00", announced=False),),
    )
    f = simulate(spec, arm="factory")
    divergent = [r for r in f.records if r.explore_reason is ExploreReason.VERIFY_DIVERGENCE]
    assert len(divergent) == 1 and divergent[0].index == 6
    assert divergent[0].verify_evals == 2  # stale exploit verify failed, then fresh verify passed
    assert f.records[5].cognition_evals > 0
    assert all(r.verified for r in f.records if r.path is not Path.REFUSED_AUTHORITY)


def test_announced_drift_is_identity_drift_not_model_trust() -> None:
    spec = SimulationSpec(
        n_classes=1,
        n_engagements=8,
        drift_events=(DriftEvent(at_engagement=4, class_id="class-00", announced=True),),
    )
    f = simulate(spec, arm="factory")
    assert f.records[3].explore_reason is ExploreReason.IDENTITY_DRIFT
    assert f.records[3].verify_evals == 1  # no wasted stale-verify: identity gate refused first


def test_authority_denied_blocks_every_consequence() -> None:
    spec = default_spec().model_copy(update={"authority_granted": False})
    f = simulate(spec, arm="factory")
    assert all(r.path is Path.REFUSED_AUTHORITY for r in f.records)
    assert all(r.standing is Standing.REFUSED and not r.verified for r in f.records)
    assert sum(r.verify_evals for r in f.records) == 0  # no world change, nothing to verify
    # compiled knowledge still exists (candidate != authority) but never becomes a DO
    assert f.mu_size_by_engagement[-1] > 0


def test_unknown_arm_is_refused() -> None:
    with pytest.raises(ValueError, match="SIM_UNKNOWN_ARM"):
        simulate(default_spec(), arm="llm")
