"""Per-gym standing, derived PURELY from real OCEL 2.0 event logs -- never
from a Python-level return value, a mocked collaborator, or anything narrated
in chat.

This is deliberately a different, stricter proof than the rest of the test
suite. A provider's own unit tests (e.g. tests/test_inspect_evals.py) can
legitimately pass while proving only that the provider's Python API behaves
correctly given its inputs -- that is unit-level Chicago-style testing done
right, not a defect. It says nothing about whether a real end-to-end episode
was actually run and independently verified.

Chicago style, applied precisely: assert on real final state, using real
collaborators, not on a hardcoded expected value and not on a helper's own
packaged verdict as an unquestioned oracle. So this module does NOT call
`scripts/ocel_standing.py`'s `_derive_one` and compare its returned string to
a literal like `"GYMACT_ACTUATED"` -- that would just be re-trusting one
script's own summary, one level removed from the log itself, the same
mistake this repo's consequence law forbids for actuator success reports.

Instead each test performs the real derivation steps itself, directly
against the real log file, using the same real collaborators
`scripts/ocel_standing.py` uses (`gymact.ocel.validate_ocel_log`, the real
official OCEL 2.0 JSON Schema; `gymact.process.ConformanceChecker`, a real
replay of the extracted operation sequence) and asserts on the real
resulting state at each step: schema validity, conformant replay, and the
real `solved=True` evidence recorded on a real `act` event's own attributes
-- not a re-derived label.

A gym with a `reports/ocel/<subject>/episode.ocel.json` log that does not
carry real solved=True, conformant-replay evidence SHOULD fail here. That
failure is the correct, useful signal -- it names a real, specific gap (a
missing dependency, an unverified plan, a nonconformant replay) instead of
leaving it undiscoverable behind a green pytest run that never checked this
axis. A red test naming a real gap is strictly preferable to a green suite
that is silent about it.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema.exceptions import ValidationError

from gymact.models import Operation
from gymact.ocel import validate_ocel_log
from gymact.process import ConformanceChecker

REPO_ROOT = Path(__file__).resolve().parents[1]
OCEL_REPORTS_DIR = REPO_ROOT / "reports" / "ocel"


def _discover_ocel_logs() -> list[Path]:
    if not OCEL_REPORTS_DIR.is_dir():
        return []
    return sorted(OCEL_REPORTS_DIR.glob("*/episode.ocel.json"))


def _reason_attribute(event: dict) -> str | None:
    for attribute in event["attributes"]:
        if attribute["name"] == "reason":
            return attribute["value"]
    return None


_LOG_PATHS = _discover_ocel_logs()
_LOG_IDS = [p.parent.name for p in _LOG_PATHS]


@pytest.mark.skipif(
    not _LOG_PATHS,
    reason="no reports/ocel/*/episode.ocel.json present in this checkout",
)
@pytest.mark.parametrize("log_path", _LOG_PATHS, ids=_LOG_IDS)
def test_gym_is_actuated_per_its_real_ocel_log(log_path: Path) -> None:
    subject = log_path.parent.name
    log = json.loads(log_path.read_bytes())

    # 1. Real schema validation against the real official OCEL 2.0 schema --
    #    not assumed, not skipped.
    try:
        validate_ocel_log(log)
    except ValidationError as exc:
        pytest.fail(f"{subject}: OCEL log is not schema-valid: {exc.message}")

    # 2. Real replay of the real extracted operation sequence, in real
    #    recorded time order -- not the order events happen to appear in
    #    the file.
    events_by_time = sorted(log["events"], key=lambda e: e["time"])
    try:
        operations = [Operation(e["type"]) for e in events_by_time]
    except ValueError as exc:
        pytest.fail(f"{subject}: log contains an unrecognized operation type: {exc}")

    conformance = ConformanceChecker().check(operations)
    assert conformance.conformant, (
        f"{subject}: nonconformant replay: "
        f"{'; '.join(d.reason for d in conformance.deviations)}"
    )

    # 3. Real solved=True evidence, read directly off a real `act` event's
    #    own attributes -- not a summary string produced by another script.
    act_events = [e for e in events_by_time if e["type"] == "act"]
    assert act_events, f"{subject}: conformant replay but no real `act` event present"

    solved_reasons: list[str] = [
        reason for e in act_events if (reason := _reason_attribute(e)) is not None
    ]
    assert any("solved=True" in reason for reason in solved_reasons), (
        f"{subject}: {len(act_events)} real act event(s), none carry "
        f"solved=True evidence; recorded reasons: {solved_reasons!r}"
    )
