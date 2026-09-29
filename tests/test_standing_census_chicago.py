"""Chicago-style tests for `scripts/standing_census.py`.

Every OCEL log here is built through the real kernel + `write_ocel_log`
(a real `MemoryProvider` episode under a real `AllowListAuthorityResolver`),
written to a tmp reports root, and classified by the census. Assertions are
made on independently re-derived state (a direct `validate_ocel_log` call, the
raw JSON of the `act` event) and on the census' returned classification -- no
mocks, no monkeypatching, no hardcoded verdict copied from a golden run.

pytest-passing != actuated: these tests prove the *classifier* discriminates;
they say nothing about whether any repo gym has been actuated.
"""

from __future__ import annotations

import copy
import importlib.util
import json
import re
import sys
from pathlib import Path
from typing import Any

import anyio
import pytest
from jsonschema.exceptions import ValidationError

from gymact import (
    ActuationIntent,
    AllowListAuthorityResolver,
    GymAct,
    MaterializationIntent,
    MemoryProvider,
    registry,
)
from gymact.models import Receipt
from gymact.ocel import validate_ocel_log, write_ocel_log

REPO_ROOT = Path(__file__).resolve().parents[1]
_SPEC = importlib.util.spec_from_file_location(
    "standing_census", REPO_ROOT / "scripts" / "standing_census.py"
)
assert _SPEC is not None and _SPEC.loader is not None
census_mod = importlib.util.module_from_spec(_SPEC)
sys.modules["standing_census"] = census_mod
_SPEC.loader.exec_module(census_mod)

AUTHORITY = "urn:test:authority"
SET_CAPABILITY = "urn:gymact:memory:capability:set"


async def _memory_episode(*, with_act: bool = True) -> list[Receipt]:
    gym = GymAct(authority_resolver=AllowListAuthorityResolver({AUTHORITY}))
    gym.register_provider(MemoryProvider())
    materialized = await gym.materialize(
        MaterializationIntent(
            provider="memory",
            config={"initial": {}, "requires_authority": True},
            authority_ref=AUTHORITY,
        )
    )
    assert materialized.accepted and materialized.episode is not None
    episode_id = materialized.episode.episode_id
    if with_act:
        acted = await gym.act(
            ActuationIntent(
                episode_id=episode_id,
                capability=SET_CAPABILITY,
                payload={"key": "k", "value": 1},
                authority_ref=AUTHORITY,
            )
        )
        assert acted.accepted
        verified = await gym.verify(episode_id, {"k": 1})
        assert verified.passed
    await gym.teardown(episode_id, authority_ref=AUTHORITY)
    return gym.episode_receipts(episode_id)


def _receipts(*, with_act: bool = True) -> list[Receipt]:
    return anyio.run(lambda: _memory_episode(with_act=with_act))


def _mark_act(receipts: list[Receipt], reason: str) -> list[Receipt]:
    """Record real outcome evidence on the act receipt (the repo's episode-script convention)."""
    return [
        r.model_copy(update={"reason": reason}) if r.operation.value == "act" else r
        for r in receipts
    ]


def _write(reports: Path, subject: str, receipts: list[Receipt]) -> Path:
    path = reports / subject / "episode.ocel.json"
    path.parent.mkdir(parents=True)
    write_ocel_log(path, receipts)
    return path


def _classify(path: Path) -> dict[str, Any]:
    return census_mod.classify_log(path)


def test_solved_conformant_valid_memory_episode_is_actuated(tmp_path: Path) -> None:
    path = _write(tmp_path, "memory", _mark_act(_receipts(), "solved=True"))
    result = _classify(path)

    # Independent re-derivation from the raw log, not from the census' verdict.
    raw = json.loads(path.read_bytes())
    validate_ocel_log(raw)
    act_reasons = [
        a["value"]
        for e in raw["events"]
        if e["type"] == "act"
        for a in e["attributes"]
        if a["name"] == "reason"
    ]
    assert act_reasons == ["solved=True"]

    assert result["standing"] == census_mod.ACTUATED
    assert result["schema_valid"] is True
    assert result["conformant"] is True
    assert (result["act_events"], result["solved_act_events"]) == (1, 1)
    assert result["sha256"] is not None


def test_unmodified_kernel_receipts_carry_no_solved_evidence(tmp_path: Path) -> None:
    """Real kernel act receipts never set `reason`: schema+replay pass, still a named gap."""
    path = _write(tmp_path, "memory", _receipts())
    raw = json.loads(path.read_bytes())
    validate_ocel_log(raw)
    assert not any(
        a["name"] == "reason" for e in raw["events"] if e["type"] == "act" for a in e["attributes"]
    )
    result = _classify(path)
    assert result["standing"] == "NO_SOLVED_ACT"
    assert result["schema_valid"] is True and result["conformant"] is True
    assert result["act_events"] == 1 and result["solved_act_events"] == 0


def test_solved_false_reason_is_not_actuated(tmp_path: Path) -> None:
    path = _write(tmp_path, "memory", _mark_act(_receipts(), "solved=False returncode=1"))
    result = _classify(path)
    assert result["standing"] == "NO_SOLVED_ACT"
    assert "solved=False" in result["detail"]


def test_schema_corrupted_copy_is_schema_invalid(tmp_path: Path) -> None:
    good = _write(tmp_path / "good", "memory", _mark_act(_receipts(), "solved=True"))
    corrupted = json.loads(good.read_bytes())
    del corrupted["events"][0]["time"]
    bad_path = tmp_path / "bad" / "memory" / "episode.ocel.json"
    bad_path.parent.mkdir(parents=True)
    bad_path.write_text(json.dumps(corrupted))

    with pytest.raises(ValidationError):
        validate_ocel_log(corrupted)
    assert _classify(good)["standing"] == census_mod.ACTUATED
    result = _classify(bad_path)
    assert result["standing"] == "SCHEMA_INVALID"
    assert result["schema_valid"] is False
    assert result["conformant"] is None


def test_nonconformant_replay_is_named_gap(tmp_path: Path) -> None:
    good = _write(tmp_path / "good", "memory", _mark_act(_receipts(), "solved=True"))
    log = json.loads(good.read_bytes())
    # Real recorded event time order decides replay: put teardown before everything.
    reordered = copy.deepcopy(log)
    for event in reordered["events"]:
        event["time"] = {
            "teardown": "2000-01-01T00:00:00+00:00",
            "materialize": "2000-01-02T00:00:00+00:00",
        }.get(event["type"], "2000-01-03T00:00:00+00:00")
    bad_path = tmp_path / "bad" / "memory" / "episode.ocel.json"
    bad_path.parent.mkdir(parents=True)
    bad_path.write_text(json.dumps(reordered))

    validate_ocel_log(reordered)  # still schema-valid: the gap is replay only
    result = _classify(bad_path)
    assert result["standing"] == "NONCONFORMANT"
    assert result["schema_valid"] is True
    assert result["conformant"] is False


def test_log_without_act_event_is_named_gap(tmp_path: Path) -> None:
    path = _write(tmp_path, "memory", _receipts(with_act=False))
    raw = json.loads(path.read_bytes())
    assert "act" not in {e["type"] for e in raw["events"]}
    assert _classify(path)["standing"] == "NO_ACT_EVENT"


def test_unparseable_log_is_named_gap(tmp_path: Path) -> None:
    path = tmp_path / "memory" / "episode.ocel.json"
    path.parent.mkdir()
    path.write_text("{not json")
    assert _classify(path)["standing"] == "UNREADABLE_LOG"


def test_missing_log_is_not_run(tmp_path: Path) -> None:
    result = _classify(tmp_path / "memory" / "episode.ocel.json")
    assert result["standing"] == census_mod.NOT_RUN
    assert result["log_exists"] is False
    assert result["sha256"] is None


def test_build_census_counts_each_class_from_injected_roots(tmp_path: Path) -> None:
    reports, tests = tmp_path / "reports", tmp_path / "tests"
    tests.mkdir()
    (tests / "test_alpha_extra.py").write_text("")
    _write(reports, "alpha", _mark_act(_receipts(), "solved=True"))
    _write(reports, "beta", _mark_act(_receipts(), "solved=False"))
    _write(reports, "gammas", _mark_act(_receipts(), "solved=True"))
    roster = [
        {"subject": s, "registered": True, "provider_class": f"{s}P", "test_stems": [s]}
        for s in ("alpha", "beta", "gamma", "delta")
    ]

    census = census_mod.build_census(reports, tests, roster)
    by_subject = {s["subject"]: s for s in census["subjects"]}
    assert by_subject["alpha"]["standing"] == "ACTUATED"
    assert by_subject["alpha"]["test_files"] == ["test_alpha_extra.py"]
    assert by_subject["beta"]["standing"] == "NO_SOLVED_ACT"
    assert by_subject["gamma"]["standing"] == "NOT_RUN"
    assert by_subject["delta"]["standing"] == "NOT_RUN"
    assert by_subject["beta"]["has_test_file"] is False

    summary = census["summary"]
    assert summary["providers"] == 4
    assert (summary["actuated"], summary["not_run"], summary["named_gap"]) == (1, 2, 1)
    assert summary["has_test_file"] == 1
    assert summary["test_file_but_not_actuated"] == 0
    # A log under a non-roster directory is reported, never credited to a roster subject.
    assert [o["subject"] for o in census["orphan_logs"]] == ["gammas"]
    assert census["orphan_logs"][0]["possible_roster_alias"] == ["gamma"]
    assert summary["orphan_actuated"] == 1


def test_test_file_without_ocel_log_is_not_actuated(tmp_path: Path) -> None:
    reports, tests = tmp_path / "reports", tmp_path / "tests"
    reports.mkdir()
    tests.mkdir()
    (tests / "test_alpha.py").write_text("def test_x():\n    assert True\n")
    roster = [
        {"subject": "alpha", "registered": True, "provider_class": "A", "test_stems": ["alpha"]}
    ]
    subject = census_mod.build_census(reports, tests, roster)["subjects"][0]
    assert subject["has_test_file"] is True
    assert subject["standing"] == "NOT_RUN"
    assert census_mod.build_census(reports, tests, roster)["summary"]["actuated"] == 0


def test_real_roster_covers_registry_and_every_gyms_provider_class() -> None:
    roster = census_mod.discover_roster()
    subjects = {r["subject"] for r in roster}
    classes = {r["provider_class"] for r in roster}
    assert set(registry.builtin_provider_names()) <= subjects
    # Independent source scan (regex, not the census' AST walk).
    declared = set()
    for path in (REPO_ROOT / "src" / "gymact" / "gyms").glob("*.py"):
        declared |= set(re.findall(r"^class (\w+Provider)\b", path.read_text(), re.M))
    assert declared <= classes
    assert len(subjects) == len(roster)  # no subject collisions


def test_cli_json_and_markdown_on_injected_reports_root(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    reports = tmp_path / "reports"
    _write(reports, "memory", _mark_act(_receipts(), "solved=True"))

    assert census_mod.main(["--json", "--reports-dir", str(reports)]) == 0
    payload = json.loads(capsys.readouterr().out)
    memory = next(s for s in payload["subjects"] if s["subject"] == "memory")
    assert memory["standing"] == "ACTUATED"
    assert payload["summary"]["actuated"] == 1

    assert census_mod.main(["--markdown", "--reports-dir", str(reports)]) == 0
    text = capsys.readouterr().out
    assert "pytest-passing != actuated" in text
    assert "| memory | True | MemoryProvider | ACTUATED |" in text
    assert re.search(r"Tree git HEAD: `[0-9a-f]{7,}|unknown`", text)


@pytest.mark.parametrize(
    ("reason", "expected"),
    [
        ("solved=True", True),
        ("returncode=0 solved=True", True),
        ("solved=True; returncode=0", True),
        ("solved=False", False),
        ("solved=False; solved=True", False),  # contradictory: fail closed
        ("solved=True solved=False", False),
        ("unsolved=True", False),  # not a whole token
        ("xsolved=True", False),
        ("solved=Trueish", False),
        ("", False),
        ("no evidence here", False),
    ],
)
def test_reason_is_solved_is_whole_token_and_fails_closed(reason: str, expected: bool) -> None:
    assert census_mod.reason_is_solved(reason) is expected
