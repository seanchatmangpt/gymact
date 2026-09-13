# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Real DECLARE constraint mining and conformance checking for gymact POWL
sessions, via a real `wpm` (wasm4pm-cli) subprocess -- not gymact's own
hand-rolled structural-fire conformance in `gymact.powl.conformance`.

Why a second, independent conformance path
--------------------------------------------
`gymact.powl.conformance.check_ocel_conformance` answers "is this observed
sequence a legal replay of *this* POWL model's own executor?" -- structural
conformance against a known model. This module answers a different
question DECLARE was built for (Pesic & van der Aalst 2008): "what
constraints does a *corpus* of prior sessions imply ('after A, B must
eventually follow'; 'A and B never co-occur'; ...), and does a *new*
session's log violate any of them?" -- declarative conformance mined from
data, with no POWL model in the loop at all. The two are complementary, not
redundant: this module can flag a session as anomalous relative to
historical behavior even when it replays its own POWL model perfectly (a
legal-but-unusual path), which structural replay conformance cannot detect.

Real subprocess, real binary, same convention as
`docs/architecture.md`'s already-documented `wpm receipt verify-ocel2`
cross-validation of `gymact.ocel`/`receipts_to_ocel`: this repo shells out
to wasm4pm's actual compiled `wpm` CLI (via `cargo run --bin wpm --`,
matching `tests/test_ggen_legacy_gym.py`'s own real-subprocess pattern) --
no PyO3 bindings, no vendored copy of the Rust mining algorithm. wasm4pm's
own real DECLARE miner (`wasm4pm::discovery::discover_declare_from_log`)
and real per-constraint conformance checker
(`wasm4pm::declare_conformance::check_declare_conformance_pure`), wired
into the CLI as `wpm mining mine-declare` / `wpm mining conformance-declare`,
are the actual algorithms that run -- this module only marshals gymact's
own OCEL 2.0 logs (`GymactOcelSessionRecorder.close()` /
`gymact.ocel.write_ocel_log`) into files `wpm` can read and parses its real
JSON output back.

Activity key: gymact's OCEL events (`gymact.powl.ocel_bridge.
GymactOcelSessionRecorder.record`) carry the fired POWL label in an event
attribute named `"detail"` (see `gymact.powl.conformance.
observed_labels_from_events`), not in the event `type` (which is always one
of `"powl_structural_fire"`/`"powl_action_binding_error"`). `wpm`'s OCEL
flattener always writes `concept:name = event type`, so mining/conformance
here must be run with `--activity-key detail` to see the actual fired
labels rather than the two constant event-type strings -- passing
`activity_key="type"` or the default `"concept:name"` would (correctly, not
a bug) mine trivial always-true constraints over one or two constant
labels.

Object type: `GymactOcelSessionRecorder` links every event to exactly one
session object of type `"PowlSession"` (plus, optionally, other domain
objects) -- one trace per session when flattened, which is the DECLARE
mining unit this module wants ("does session N's constraint profile match
what prior sessions established").
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

__all__ = [
    "DeclareConstraintViolation",
    "DeclareConformanceReport",
    "WASM4PM_ROOT",
    "wasm4pm_available",
    "mine_declare_constraints",
    "check_declare_conformance",
]

WASM4PM_ROOT = Path(os.environ.get("WASM4PM_ROOT", str(Path.home() / "wasm4pm"))).resolve()

_DEFAULT_ACTIVITY_KEY = "detail"
_DEFAULT_OBJECT_TYPE = "PowlSession"
_SUBPROCESS_TIMEOUT_SECONDS = 300


def wasm4pm_available() -> bool:
    """True iff a real wasm4pm checkout with `cargo run --bin wpm` is
    usable -- the same availability check
    `tests/test_ggen_legacy_gym.py::test_ocel_export_is_independently_validated_by_wasm4pm`
    already uses for its `wpm receipt verify-ocel2` cross-validation."""
    return (WASM4PM_ROOT / "Cargo.toml").is_file() and shutil.which("cargo") is not None


@dataclass(frozen=True)
class DeclareConstraintViolation:
    """One real mined DECLARE constraint's conformance result against a
    checked log -- not a boolean, the actual per-constraint violation
    count and fitness `wpm mining conformance-declare` reports."""

    template: str
    activities: tuple[str, ...]
    support: float
    violations: int
    fitness: float

    @property
    def is_violated(self) -> bool:
        return self.violations > 0


@dataclass(frozen=True)
class DeclareConformanceReport:
    """Real parsed output of `wpm mining conformance-declare`."""

    total_traces: int
    avg_fitness: float
    constraints: tuple[DeclareConstraintViolation, ...] = field(default_factory=tuple)

    @property
    def violated_constraints(self) -> tuple[DeclareConstraintViolation, ...]:
        return tuple(c for c in self.constraints if c.is_violated)


def _run_wpm(args: list[str]) -> subprocess.CompletedProcess[str]:
    """Real subprocess invocation of wasm4pm's `wpm` CLI. Same
    `cargo run --bin wpm --` + `cwd=WASM4PM_ROOT` convention as
    `tests/test_ggen_legacy_gym.py` -- `cwd` (not `--manifest-path`) is
    required so rustup resolves wasm4pm-compat's pinned nightly toolchain
    file, exactly as that test's own comment documents."""
    return subprocess.run(
        ["cargo", "run", "--bin", "wpm", "--", *args],
        cwd=str(WASM4PM_ROOT),
        capture_output=True,
        text=True,
        timeout=_SUBPROCESS_TIMEOUT_SECONDS,
    )


def _write_ocel_temp(ocel_log: dict[str, Any], dest: Path) -> Path:
    dest.write_text(json.dumps(ocel_log))
    return dest


def mine_declare_constraints(
    ocel_log: dict[str, Any],
    *,
    workdir: Path,
    activity_key: str = _DEFAULT_ACTIVITY_KEY,
    object_type: str = _DEFAULT_OBJECT_TYPE,
) -> Path:
    """Mine a real DECLARE constraint model from a real gymact OCEL 2.0 log
    (as produced by `GymactOcelSessionRecorder.close()` or
    `gymact.ocel.write_ocel_log`'s in-memory `log` dict) via a real `wpm
    mining mine-declare` subprocess.

    Returns the path to the written DeclareModel JSON file (in `workdir`),
    for use as the `model` argument to `check_declare_conformance`.

    Raises `RuntimeError` (with real stdout/stderr attached) on any real
    subprocess failure -- never returns a placeholder model.
    """
    log_path = _write_ocel_temp(ocel_log, workdir / "declare_mine_input.ocel.json")
    model_path = workdir / "declare_model.json"

    result = _run_wpm(
        [
            "mining",
            "mine-declare",
            str(log_path),
            "--activity-key",
            activity_key,
            "--object-type",
            object_type,
            "-o",
            str(model_path),
        ]
    )
    if result.returncode != 0 or not model_path.is_file():
        raise RuntimeError(
            "wpm mining mine-declare failed "
            f"(exit={result.returncode}):\nstdout={result.stdout}\nstderr={result.stderr}"
        )
    return model_path


def check_declare_conformance(
    ocel_log: dict[str, Any],
    declare_model_path: Path,
    *,
    workdir: Path,
    activity_key: str = _DEFAULT_ACTIVITY_KEY,
    object_type: str = _DEFAULT_OBJECT_TYPE,
) -> DeclareConformanceReport:
    """Check a real gymact OCEL 2.0 session log against a real mined
    DECLARE model (from `mine_declare_constraints`) via a real `wpm mining
    conformance-declare` subprocess. Returns the real per-constraint
    violation records `wpm` computed -- never a boolean, never a
    fabricated/synthetic report.
    """
    log_path = _write_ocel_temp(ocel_log, workdir / "declare_check_input.ocel.json")

    result = _run_wpm(
        [
            "mining",
            "conformance-declare",
            str(log_path),
            str(declare_model_path),
            "--activity-key",
            activity_key,
            "--object-type",
            object_type,
        ]
    )
    if result.returncode != 0:
        raise RuntimeError(
            "wpm mining conformance-declare failed "
            f"(exit={result.returncode}):\nstdout={result.stdout}\nstderr={result.stderr}"
        )

    # `wpm`'s stdout is `[info logs]* + one JSON line` when no `-o` is
    # given; take the last non-empty line, which is the real report.
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    if not lines:
        raise RuntimeError(
            f"wpm mining conformance-declare produced no output:\nstderr={result.stderr}"
        )
    payload = json.loads(lines[-1])

    constraints = tuple(
        DeclareConstraintViolation(
            template=c["template"],
            activities=tuple(c["activities"]),
            support=c["support"],
            violations=c["violations"],
            fitness=c["fitness"],
        )
        for c in payload.get("constraints", [])
    )
    return DeclareConformanceReport(
        total_traces=payload["total_traces"],
        avg_fitness=payload["avg_fitness"],
        constraints=constraints,
    )
