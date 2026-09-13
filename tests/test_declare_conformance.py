# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Chicago-style (real subprocess, real POWL runner, no mocks) integration
test for `gymact.powl.declare_conformance`.

Drives two real `gymact.powl.runner.run_pipeline` sessions to completion
(producing two real OCEL 2.0 logs via the real `GymactOcelSessionRecorder`),
mines a real DECLARE constraint model from the first session's log via a
real `wpm mining mine-declare` subprocess, and checks the second session's
real log against those mined constraints via a real `wpm mining
conformance-declare` subprocess -- asserting on the real returned
violation-record content, not a boolean.

Skip (not mock) convention matches
`tests/test_ggen_legacy_gym.py::test_ocel_export_is_independently_validated_by_wasm4pm`:
this module has no real fallback for a missing wasm4pm checkout, so it
degrades to a named, visible `require_standing` skip rather than mocking
the subprocess boundary.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from gymact.powl.algebra import Atom, OrderEdge, PartialOrder
from gymact.powl.declare_conformance import (
    WASM4PM_ROOT,
    check_declare_conformance,
    mine_declare_constraints,
    wasm4pm_available,
)
from gymact.powl.runner import run_pipeline
from gymact.powl.spec import PowlPipelineSpec
from gymact.standing import require_standing

_SPEC = PowlPipelineSpec(
    readonly_labels=frozenset({"step_a", "step_b", "step_c"}),
    default_session_id="declare-conformance-fixture",
)


def _conforming_model() -> PartialOrder:
    """A->B->C, strictly ordered -- every real session driven through this
    model fires "step_a", "step_b", "step_c" in that exact order."""
    return PartialOrder(
        children=(Atom("step_a"), Atom("step_b"), Atom("step_c")),
        order=frozenset({OrderEdge(0, 1), OrderEdge(1, 2)}),
    )


def _run_real_session(session_id: str) -> dict:
    """Drives one real `run_pipeline` session to completion and returns its
    real, validated OCEL 2.0 log (`recorder.close()`'s output)."""
    log, stall = run_pipeline(
        _conforming_model(),
        spec=_SPEC,
        session_id=session_id,
        allow_partial_bindings=True,
    )
    assert stall.final, f"session {session_id} did not complete: {stall}"
    return log


def test_declare_mining_and_conformance_over_two_real_powl_sessions(tmp_path: Path) -> None:
    require_standing(
        "LOCAL_CHECKOUT:wasm4pm",
        available=wasm4pm_available(),
        reason=f"no wasm4pm checkout with cargo available at {WASM4PM_ROOT}",
    )

    # Two independent real sessions, both driven through the same
    # strictly-ordered A->B->C model -- real production code
    # (`gymact.powl.runner.run_pipeline` + `GymactOcelSessionRecorder`), not
    # hand-built JSON fixtures.
    mining_corpus_log = _run_real_session("declare-mining-corpus")
    check_log = _run_real_session("declare-check-target")

    assert mining_corpus_log["events"], "mining corpus session recorded no events"
    assert check_log["events"], "check-target session recorded no events"

    model_path = mine_declare_constraints(mining_corpus_log, workdir=tmp_path)
    assert model_path.is_file()

    report = check_declare_conformance(check_log, model_path, workdir=tmp_path)

    # Real assertions on the real returned report content -- not a boolean.
    assert report.total_traces >= 1
    assert report.constraints, "wpm mined zero DECLARE constraints from the corpus session"

    # Both sessions fire the identical strict A->B->C sequence, so the
    # second session's real log must conform to every constraint mined from
    # the first: zero real violations, average fitness 1.0.
    assert report.violated_constraints == ()
    assert report.avg_fitness == pytest.approx(1.0)

    templates = {c.template for c in report.constraints}
    # The strict total order across three always-co-occurring activities
    # must yield at least a real Precedence or Succession constraint --
    # confirms real sequence structure was mined, not just per-activity
    # Existence.
    assert templates & {"Precedence", "Succession", "Response", "ChainResponse"}


def test_declare_conformance_detects_a_real_out_of_order_violation(tmp_path: Path) -> None:
    require_standing(
        "LOCAL_CHECKOUT:wasm4pm",
        available=wasm4pm_available(),
        reason=f"no wasm4pm checkout with cargo available at {WASM4PM_ROOT}",
    )

    mining_corpus_log = _run_real_session("declare-mining-corpus-2")
    model_path = mine_declare_constraints(mining_corpus_log, workdir=tmp_path)

    # A second, genuinely different real model (B->A, reversed order) run
    # through the same real runner -- a real violating session, not a
    # hand-edited log.
    reversed_model = PartialOrder(
        children=(Atom("step_b"), Atom("step_a")),
        order=frozenset({OrderEdge(0, 1)}),
    )
    violating_log, stall = run_pipeline(
        reversed_model,
        spec=_SPEC,
        session_id="declare-violating-session",
        allow_partial_bindings=True,
    )
    assert stall.final

    report = check_declare_conformance(violating_log, model_path, workdir=tmp_path)

    assert report.violated_constraints, (
        "expected the reversed-order session to violate at least one real "
        "constraint mined from the strictly-ordered corpus"
    )
    assert report.avg_fitness < 1.0
