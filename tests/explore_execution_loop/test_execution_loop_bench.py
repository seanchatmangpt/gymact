"""Benchmark regression court for the ALOOP execution kernel.

Runs the real benchmark script (``scripts/bench_execution_loop.py``) against
the real kernel and enforces two bounds:

1. Structural (exact, deterministic): events / claims / actuations / virtual
   ticks per episode class are pinned. Extra work per episode -- another
   claim, another actuation, another event -- fails here regardless of
   machine speed.
2. Wall-clock (generous): the fastest episode of every class stays under
   ``CEILING_US_PER_EPISODE`` and within ``MAX_RATIO_TO_HEALTHY`` of the
   healthy class (fastest samples; see the script). The committed receipt
   ``receipts/v26.9.26/execution-loop-bench.json`` records the measured
   numbers and must describe the same structural profile as the live kernel.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

from gymact.evidence import digest

ROOT = Path(__file__).parents[2]
SCRIPT = ROOT / "scripts" / "bench_execution_loop.py"
RECEIPT = ROOT / "receipts" / "v26.9.26" / "execution-loop-bench.json"

_spec = importlib.util.spec_from_file_location("bench_execution_loop", SCRIPT)
assert _spec is not None and _spec.loader is not None
bench = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bench)

EXPECTED_PROFILE = {
    "healthy": {
        "outcome": "Recover",
        "standing": "ALIVE",
        "events": 5,  # includes the kernel-emitted actuation event
        "claims": 1,
        "actuations": 1,
        "result_actuation_count": 1,
        "virtual_ticks": 1,
    },
    "substitute": {
        "outcome": "Recover",
        "standing": "ALIVE",
        "events": 13,  # includes the kernel-emitted actuation event
        "claims": 5,
        "actuations": 1,
        "result_actuation_count": 1,
        "virtual_ticks": 4,
    },
    "crash_journal": {
        "outcome": "Recover",
        "standing": "ALIVE",
        "events": 7,  # journal-fragment verification + journal-witnessed actuation
        "claims": 1,
        "actuations": 1,
        "result_actuation_count": 1,
        "virtual_ticks": 1,
    },
    "dedupe": {
        "outcome": "Recover",
        "standing": "ALIVE",
        "events": 1,
        "claims": 1,
        "actuations": 1,
        "result_actuation_count": 0,
        "virtual_ticks": 1,
    },
}


def test_structural_profile_is_pinned():
    assert bench.structural_profile() == EXPECTED_PROFILE


def test_structural_profile_is_deterministic_across_runs():
    assert digest(bench.structural_profile()) == digest(bench.structural_profile())


def test_fastest_episode_times_are_within_bounds():
    for kind in bench.CLASSES:
        bench.run_episode(kind)  # warm-up
    timings = {kind: bench.time_class(kind, 200) for kind in bench.CLASSES}
    assert bench.violations(timings) == {}, timings


def test_bound_checker_refuses_a_slow_fault_path():
    """Anti-vacuity: the bound function must actually fire."""
    healthy = {"min_ns": 100_000.0}
    slow_ratio = {"min_ns": 100_000.0 * (bench.MAX_RATIO_TO_HEALTHY + 1)}
    slow_abs = {"min_ns": bench.CEILING_US_PER_EPISODE * 1000 + 1.0}
    assert set(bench.violations({"healthy": healthy, "substitute": slow_ratio})) == {"substitute"}
    assert "healthy" in bench.violations({"healthy": slow_abs})


def test_committed_receipt_matches_live_kernel():
    receipt = json.loads(RECEIPT.read_text())
    assert receipt["schema"] == "gymact/execution-loop-bench/1"
    assert receipt["authority"] == "NONE"
    assert receipt["within_ceiling"] is True
    assert receipt["structural_profile"] == EXPECTED_PROFILE
    assert receipt["structural_digest"] == digest(EXPECTED_PROFILE)
    for kind in bench.CLASSES:
        timing = receipt["timings"][kind]
        assert timing["episodes"] >= 1000
        assert 0 < timing["min_ns"] <= receipt["ceiling_us_per_episode"] * 1000
    assert receipt["violations"] == {}


def test_benchmark_script_runs_as_a_real_process(tmp_path):
    out = tmp_path / "bench.json"
    completed = subprocess.run(
        [sys.executable, str(SCRIPT), "--episodes", "50", "--out", str(out)],
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    assert completed.returncode == 0, completed.stderr
    produced = json.loads(out.read_text())
    assert produced["structural_profile"] == EXPECTED_PROFILE
    assert produced["within_ceiling"] is True
