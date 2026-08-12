# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Chicago-style tests for `gymact.combinatorial_ocel` -- the bridge
between the real Design-for-Combinatorial-Maximum engine
(`combinatorial.py`) and the real OCEL 2.0 emitter (`ocel.py`).

Real collaborators throughout: a real `GymAct` kernel driven through real
`materialize`/`act`/`observe`/`verify`/`checkpoint`/`restore`/`teardown`
calls against real, in-repo providers (`MemoryProvider`,
`LockAndKeyProvider`, `SwitchboardProvider`); the real, unmodified
`manufacture_combination_space`/`receipts_to_ocel`/`validate_ocel_log`
pipeline this module wires together, never reimplemented here.

No `unittest.mock` / `Mock` / `MagicMock` / `patch` / `monkeypatch`
anywhere in this file.
"""

from __future__ import annotations

import asyncio

import pytest

from gymact.combinatorial_ocel import (
    GYM_FACTOR,
    SEQUENCE_VARIANT_FACTOR,
    build_combination_space,
    drive_combination,
    run_combinatorial_maximum,
)
from gymact.ocel import validate_ocel_log


def test_build_combination_space_is_a_real_cartesian_product() -> None:
    """Real call into the existing, unmodified combinatorial engine --
    never a reimplementation. Cardinality must be the real product of the
    two real factor sizes."""
    space = build_combination_space()
    expected = len(GYM_FACTOR.alternatives) * len(SEQUENCE_VARIANT_FACTOR.alternatives)
    assert space.total_cardinality == expected
    assert not space.truncated
    assert len(space.combinations) == expected


def test_build_combination_space_honestly_truncates_when_bounded() -> None:
    """Per the doctrine's own law ('truncation is evidence, silent
    pruning is forbidden') -- a real, small bound must produce a real,
    honestly-flagged truncated space, never a silently-shrunk one."""
    space = build_combination_space(max_combinations=2)
    assert space.truncated is True
    assert len(space.combinations) == 2
    assert space.total_cardinality > 2


def test_drive_combination_lock_and_key_happy_path_reaches_real_alive() -> None:
    receipts, final_standing = asyncio.run(drive_combination("lock-and-key", "happy_path"))
    assert len(receipts) > 0
    assert final_standing == "ALIVE"


def test_drive_combination_memory_reaches_real_refused_fail_closed_authority() -> None:
    """Named, not hidden: MemoryProvider's real DO capabilities require
    authority by default, and GymAct()'s default DenyAuthorityResolver
    is fail-closed. This is a real, correct refusal, not a bug -- pinned
    here so a future change that silently starts admitting these calls
    (weakening the fail-closed default) is caught."""
    receipts, final_standing = asyncio.run(drive_combination("memory", "happy_path"))
    assert len(receipts) > 0
    assert final_standing == "REFUSED"
    assert receipts[-1].reason == "LIVE_AUTHORITY_REQUIRED"


def test_drive_combination_switchboard_with_checkpoint_restore_is_real() -> None:
    receipts, final_standing = asyncio.run(drive_combination("switchboard", "with_checkpoint_restore"))
    assert len(receipts) >= 3  # materialize + toggle + checkpoint/restore bookkeeping + teardown
    assert final_standing == "ALIVE"


def test_drive_combination_unknown_gym_raises() -> None:
    with pytest.raises(KeyError):
        asyncio.run(drive_combination("not-a-real-gym", "happy_path"))


def test_run_combinatorial_maximum_produces_a_real_schema_valid_ocel_log(tmp_path) -> None:
    """Real, end-to-end: drives every real combination, folds every real
    receipt into one real OCEL 2.0 log, and independently re-validates it
    against the real vendored ocel20-schema.json -- never trusting
    write_ocel_log's own success silently."""
    space, report = asyncio.run(run_combinatorial_maximum(reports_dir=tmp_path))

    assert report["combinations_run"] == space.total_cardinality
    assert report["truncated"] is False
    assert report["total_receipts"] > 0
    assert len(report["combinations"]) == report["combinations_run"]

    ocel_path = tmp_path / "episode.ocel.json"
    assert ocel_path.is_file()
    import json

    log = json.loads(ocel_path.read_text())
    validate_ocel_log(log)  # real re-validation; raises on real schema violation

    real_event_types = {t["name"] for t in log["eventTypes"]}
    assert "materialize" in real_event_types
    assert "teardown" in real_event_types
    assert "act" in real_event_types

    real_object_types = {t["name"] for t in log["objectTypes"]}
    assert "episode" in real_object_types

    report_path = tmp_path / "combination_report.json"
    assert report_path.is_file()
    persisted_report = json.loads(report_path.read_text())
    assert persisted_report["total_receipts"] == report["total_receipts"]


def test_run_combinatorial_maximum_report_rows_cross_check_the_ocel_log(tmp_path) -> None:
    """The real combination report's per-row receipt counts must sum to
    the real total receipt count folded into the OCEL log -- a real,
    checkable cross-reference, not two independently-drifting numbers."""
    _space, report = asyncio.run(run_combinatorial_maximum(reports_dir=tmp_path))
    summed = sum(row["receipt_count"] for row in report["combinations"])
    assert summed == report["total_receipts"]

    import json

    log = json.loads((tmp_path / "episode.ocel.json").read_text())
    assert len(log["events"]) == report["total_receipts"]


def test_run_combinatorial_maximum_reaches_a_real_mix_of_standings(tmp_path) -> None:
    """A combinatorial-maximum proof that only ever reaches ALIVE would
    be exactly the kind of unfalsifiable, cherry-picked result this
    doctrine exists to prevent -- assert the real run actually reaches
    more than one distinct real Standing value."""
    _space, report = asyncio.run(run_combinatorial_maximum(reports_dir=tmp_path))
    real_standings = {row["final_standing"] for row in report["combinations"]}
    assert len(real_standings) > 1, f"expected a real mix of standings, got only {real_standings}"
