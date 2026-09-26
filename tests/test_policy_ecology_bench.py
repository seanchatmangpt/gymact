"""Regression bound for the policy-ecology benchmark (real subprocess, real module).

Runs ``scripts/bench_policy_ecology.py`` as a real child process and pins:

* determinism: two runs over the seeded populations emit the same result digest
  and metrics (timings excluded);
* a throughput ceiling for ``population_diversity`` (ns per member pair) and
  ``condition_population`` (us per member).

Recorded on PR #145 (arm64, CPython 3.13, min of 5): the pre-hardening per-pair
set/dict implementation measured ~2100-2300 ns/pair; the precomputed-vector +
``math.dist`` implementation measures ~110-140 ns/pair at 64-512 members, and
conditioning ~12-18 us/member (pre-hardening ~10-15). The ceilings below sit
well above the hardened numbers (slow CI runners) but below the old diversity
path, so reintroducing per-pair axis-union construction trips the bound. Receipt:
``receipts/v26.9.26/policy-ecology-bench.json``.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "bench_policy_ecology.py"

DIVERSITY_NS_PER_PAIR_CEILING = 1000.0
CONDITION_US_PER_MEMBER_CEILING = 250.0


def _run_bench(*args: str) -> dict:
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(
        part for part in (str(ROOT / "src"), env.get("PYTHONPATH", "")) if part
    )
    completed = subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        check=True,
        capture_output=True,
        text=True,
        env=env,
        timeout=300,
    )
    return json.loads(completed.stdout)


def _metrics(report: dict) -> list[tuple[int, float, float]]:
    return [(row["members"], row["disparity"], row["complexity"]) for row in report["rows"]]


def test_bench_is_deterministic_and_within_regression_bound() -> None:
    first = _run_bench("--sizes", "64,256", "--repeat", "3")
    second = _run_bench("--sizes", "64,256", "--repeat", "1")

    assert first["result_digest"] == second["result_digest"]
    assert _metrics(first) == _metrics(second)
    assert [row["pairs"] for row in first["rows"]] == [2016, 32640]

    for row in first["rows"]:
        assert row["diversity_ns_per_pair"] < DIVERSITY_NS_PER_PAIR_CEILING, row
        assert row["condition_us_per_member"] < CONDITION_US_PER_MEMBER_CEILING, row
        # inverse-Simpson complexity is bounded by the member count
        assert 1.0 <= row["complexity"] <= row["members"]
        # nine unit axes: every pairwise distance is at most sqrt(9) = 3
        assert 0.0 < row["disparity"] <= 3.0


def test_bench_refuses_nonpositive_inputs() -> None:
    completed = subprocess.run(
        [sys.executable, str(SCRIPT), "--sizes", "0", "--repeat", "1"],
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
        timeout=60,
    )
    assert completed.returncode == 2
    assert "REFUSED:BENCH_REQUIRES_POSITIVE_SIZES_AND_REPEAT" in completed.stderr
