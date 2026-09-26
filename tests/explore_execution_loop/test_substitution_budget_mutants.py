"""Mutation court for provider substitution: the fresh retry budget is load-bearing.

``AutonomousLoop`` resets ``attempts`` to zero at both ``provider.replace``
sites (claim-time and execution-time substitution). If a mutant that drops
either reset still passed the fault corpus, the substitution scenarios would be
vacuous: they would witness the ``provider.replace`` event without witnessing
that the substituted provider actually gets its own bounded retry budget.

Each test builds a real mutant package on disk (every ``gymact`` module is a
symlink to the real source except ``execution_loop.py``, which is a copy with
one reset removed), then runs the real corpus scenario in a real subprocess
with that package first on ``PYTHONPATH``. No test doubles are involved.

The unmutated control copy must pass (proves the harness really imports the
copied package and the scenario is green), and each mutant must be killed by
its scenario.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
REAL_PACKAGE = REPO / "src" / "gymact"
CORPUS = REPO / "tests" / "explore_execution_loop" / "test_fault_corpus.py"
RESET_LINE = "attempts = 0  # fresh retry budget on the substituted provider"
MUTANT_LINE = "pass  # MUTANT: substituted provider inherits the exhausted budget"

# site index (1-based occurrence of RESET_LINE) -> corpus scenario that must kill it
SITES = {
    1: "L7-F04-provider-disappears-mid-claim",
    2: "L7-F05-provider-disappears-mid-execution",
}


def _build_package(root: Path, source: str) -> Path:
    src = root / "src"
    package = src / "gymact"
    package.mkdir(parents=True)
    for entry in REAL_PACKAGE.iterdir():
        if entry.name in {"execution_loop.py", "__pycache__"}:
            continue
        (package / entry.name).symlink_to(entry)
    (package / "execution_loop.py").write_text(source, encoding="utf-8")
    return src


def _mutate(source: str, site: int) -> str:
    parts = source.split(RESET_LINE)
    assert len(parts) - 1 == len(SITES), (
        f"expected {len(SITES)} budget-reset sites in execution_loop.py, "
        f"found {len(parts) - 1}; update SITES with the new substitution paths"
    )
    head = RESET_LINE.join(parts[:site])
    tail = RESET_LINE.join(parts[site:])
    mutated = head + MUTANT_LINE + tail
    assert mutated.count(RESET_LINE) == len(SITES) - 1
    return mutated


def _run_scenario(src: Path, scenario: str, junit: Path) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(src)
    env.pop("PYTEST_ADDOPTS", None)
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            str(CORPUS),
            "-k",
            scenario,
            "-p",
            "no:cacheprovider",
            "-q",
            f"--junitxml={junit}",
            "-c",
            str(REPO / "pyproject.toml"),
            "--rootdir",
            str(REPO),
        ],
        cwd=REPO,
        env=env,
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )


def _junit_counts(junit: Path) -> tuple[int, int]:
    text = junit.read_text(encoding="utf-8")
    header = text[text.index("<testsuite ") :].split(">", 1)[0]

    def attr(name: str) -> int:
        return int(header.split(f'{name}="', 1)[1].split('"', 1)[0])

    return attr("tests"), attr("failures") + attr("errors")


@pytest.mark.parametrize("site", sorted(SITES))
def test_control_copy_passes_scenario(tmp_path: Path, site: int) -> None:
    source = (REAL_PACKAGE / "execution_loop.py").read_text(encoding="utf-8")
    src = _build_package(tmp_path, source)
    junit = tmp_path / "junit.xml"
    proc = _run_scenario(src, SITES[site], junit)
    tests, bad = _junit_counts(junit)
    assert proc.returncode == 0, proc.stdout[-2000:] + proc.stderr[-2000:]
    assert tests >= 1 and bad == 0


@pytest.mark.parametrize("site", sorted(SITES))
def test_budget_reset_mutant_is_killed(tmp_path: Path, site: int) -> None:
    source = (REAL_PACKAGE / "execution_loop.py").read_text(encoding="utf-8")
    src = _build_package(tmp_path, _mutate(source, site))
    assert MUTANT_LINE in (src / "gymact" / "execution_loop.py").read_text(encoding="utf-8")
    junit = tmp_path / "junit.xml"
    proc = _run_scenario(src, SITES[site], junit)
    tests, bad = _junit_counts(junit)
    assert tests >= 1
    assert proc.returncode != 0 and bad >= 1, (
        f"VACUOUS SUBSTITUTION COURT: mutant site {site} (no budget reset) survived "
        f"{SITES[site]}\n{proc.stdout[-2000:]}"
    )
    assert SITES[site] in junit.read_text(encoding="utf-8")
