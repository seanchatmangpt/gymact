#!/usr/bin/env python3
"""Machine-derived census: what has GymAct actually PROVEN vs merely unit-tested.

Follows `.claude/rules/ocel-standing.md`. For every provider/gym in the roster
this computes, directly from real files and real collaborators:

  1. roster: `gymact.registry` builtins, plus every `*Provider` class defined
     in `src/gymact/gyms/*.py` (AST scan, so unregistered providers are still
     counted and named as unregistered) -- no hardcoded roster;
  2. OCEL standing from `reports/ocel/<subject>/episode.ocel.json`:
       - exists?
       - passes `gymact.ocel.validate_ocel_log` (real OCEL 2.0 JSON Schema)?
       - replays conformant via `gymact.process.ConformanceChecker`, over the
         operation sequence in real recorded event-time order?
       - has an `act` event whose own `reason` attribute carries `solved=True`?
  3. whether a `tests/test_<gym>*.py` file exists (a claim about `request
     accepted` only -- never evidence of actuation).

This deliberately does NOT call `scripts/ocel_standing.py`; the derivation is
re-done here from the log bytes. It is a measurement, not an oracle for tests:
`tests/test_standing_census_chicago.py` asserts on real derived state.

Standing vocabulary (OCEL axis):
  ACTUATED          all three OCEL conditions hold from real values
  NOT_RUN           no log for the subject
  SCHEMA_INVALID    log fails OCEL 2.0 schema validation      (named gap)
  UNREADABLE_LOG    log is not parseable JSON                 (named gap)
  UNKNOWN_OPERATION log has an event type outside Operation   (named gap)
  NONCONFORMANT     replay deviates from the process model    (named gap)
  NO_ACT_EVENT      conformant, but no `act` event            (named gap)
  NO_SOLVED_ACT     act event(s) present, none solved=True    (named gap)

Usage:
  python scripts/standing_census.py --json
  python scripts/standing_census.py --markdown
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from jsonschema.exceptions import ValidationError  # noqa: E402

from gymact import registry  # noqa: E402
from gymact.models import Operation  # noqa: E402
from gymact.ocel import validate_ocel_log  # noqa: E402
from gymact.process import ConformanceChecker  # noqa: E402

ACTUATED = "ACTUATED"
NOT_RUN = "NOT_RUN"
GAP_STANDINGS = (
    "SCHEMA_INVALID",
    "UNREADABLE_LOG",
    "UNKNOWN_OPERATION",
    "NONCONFORMANT",
    "NO_ACT_EVENT",
    "NO_SOLVED_ACT",
)
LOG_NAME = "episode.ocel.json"


_SOLVED_TOKEN = re.compile(r"(?<![A-Za-z0-9_])solved=(True|False)(?![A-Za-z0-9_])")


def reason_is_solved(reason: str) -> bool:
    """True only for a whole-token `solved=True` with no contradicting `solved=False`.

    Fail-closed: `unsolved=True` (not a whole token) and a reason that carries both
    `solved=False` and `solved=True` are NOT solved evidence.
    """
    tokens = _SOLVED_TOKEN.findall(reason)
    return "True" in tokens and "False" not in tokens


def _reason_of(event: dict[str, Any]) -> str:
    for attribute in event.get("attributes", []):
        if attribute.get("name") == "reason":
            return str(attribute.get("value"))
    return ""


def classify_log(log_path: Path) -> dict[str, Any]:
    """Derive OCEL standing for one log path, from the log's own bytes.

    A missing file is `NOT_RUN`. Every other outcome is derived from a real
    `validate_ocel_log` call, a real `ConformanceChecker` replay, and the real
    `reason` attribute of the log's own `act` events.
    """
    result: dict[str, Any] = {
        "log_path": str(log_path),
        "log_exists": log_path.is_file(),
        "schema_valid": None,
        "conformant": None,
        "act_events": None,
        "solved_act_events": None,
        "sha256": None,
        "standing": NOT_RUN,
        "detail": "no episode.ocel.json for this subject",
    }
    if not log_path.is_file():
        return result

    raw = log_path.read_bytes()
    result["sha256"] = hashlib.sha256(raw).hexdigest()
    try:
        log = json.loads(raw)
    except ValueError as exc:
        result["standing"] = "UNREADABLE_LOG"
        result["detail"] = f"not valid JSON: {exc}"
        return result

    try:
        validate_ocel_log(log)
    except ValidationError as exc:
        result["schema_valid"] = False
        result["standing"] = "SCHEMA_INVALID"
        result["detail"] = str(exc.message)
        return result
    result["schema_valid"] = True

    events = sorted(log["events"], key=lambda e: e["time"])
    try:
        operations = [Operation(e["type"]) for e in events]
    except ValueError as exc:
        result["standing"] = "UNKNOWN_OPERATION"
        result["detail"] = str(exc)
        return result

    conformance = ConformanceChecker().check(operations)
    result["conformant"] = bool(conformance.conformant)
    if not conformance.conformant:
        result["standing"] = "NONCONFORMANT"
        result["detail"] = "; ".join(d.reason for d in conformance.deviations)
        return result

    act_events = [e for e in events if e["type"] == "act"]
    solved = [e for e in act_events if reason_is_solved(_reason_of(e))]
    result["act_events"] = len(act_events)
    result["solved_act_events"] = len(solved)
    if not act_events:
        result["standing"] = "NO_ACT_EVENT"
        result["detail"] = "schema-valid, conformant, but no act event (bootstrap/read-only only)"
    elif not solved:
        reasons = sorted({r for e in act_events if (r := _reason_of(e))})
        result["standing"] = "NO_SOLVED_ACT"
        result["detail"] = (
            f"{len(act_events)} act event(s), none carry solved=True; reasons={reasons}"
        )
    else:
        result["standing"] = ACTUATED
        result["detail"] = f"{len(solved)}/{len(act_events)} act event(s) carry solved=True"
    return result


def _module_subject(stem: str) -> str:
    return stem.replace("_", "-")


def _module_stem(module: str) -> str:
    """`gymact.gyms.cloudsim.provider` -> `cloudsim`; `gymact.providers` -> `providers`."""
    parts = module.split(".")
    if parts[:2] == ["gymact", "gyms"] and len(parts) > 2:
        return parts[2]
    return parts[-1]


def _kebab_class(name: str) -> str:
    base = name.removesuffix("Provider")
    return re.sub(r"(?<!^)(?=[A-Z])", "-", base).lower()


def discover_roster(gyms_dir: Path | None = None) -> list[dict[str, Any]]:
    """Roster = registry builtins + every *Provider class under gyms/*.py.

    A registry key is the OCEL subject directory name. A Provider class not
    reachable from the registry is included with `registered=False` and its
    subject named after its module (underscores -> hyphens).
    """
    gyms_dir = gyms_dir or (REPO_ROOT / "src" / "gymact" / "gyms")
    roster: dict[str, dict[str, Any]] = {}
    registered_class_names: set[str] = set()

    for key in registry.builtin_provider_names():
        provider_type = registry._BUILTINS[key][0]
        registered_class_names.add(provider_type.__name__)
        roster[key] = {
            "subject": key,
            "registered": True,
            "provider_class": provider_type.__name__,
            "module": provider_type.__module__,
            "test_stems": sorted({key.replace("-", "_"), _module_stem(provider_type.__module__)}),
        }

    for path in sorted(gyms_dir.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in tree.body:
            if (
                isinstance(node, ast.ClassDef)
                and node.name.endswith("Provider")
                and node.name not in registered_class_names
            ):
                subject = _module_subject(path.stem)
                if subject in roster:
                    subject = _kebab_class(node.name)
                roster[subject] = {
                    "subject": subject,
                    "registered": False,
                    "provider_class": node.name,
                    "module": f"gymact.gyms.{path.stem}",
                    "test_stems": [path.stem],
                }
    return [roster[k] for k in sorted(roster)]


def find_tests(tests_dir: Path, stems: list[str]) -> list[str]:
    found: set[str] = set()
    for stem in stems:
        for match in tests_dir.glob(f"test_{stem}*.py"):
            found.add(match.name)
    return sorted(found)


def _normalize(name: str) -> str:
    return name.replace("_", "-").removesuffix("s")


def build_census(
    reports_dir: Path,
    tests_dir: Path,
    roster: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    roster = discover_roster() if roster is None else roster
    subjects: list[dict[str, Any]] = []
    for entry in roster:
        standing = classify_log(reports_dir / entry["subject"] / LOG_NAME)
        tests = find_tests(tests_dir, entry.get("test_stems", []))
        subjects.append({**entry, **standing, "test_files": tests, "has_test_file": bool(tests)})

    roster_names = {e["subject"] for e in roster}
    orphans: list[dict[str, Any]] = []
    if reports_dir.is_dir():
        for log_path in sorted(reports_dir.glob(f"*/{LOG_NAME}")):
            name = log_path.parent.name
            if name in roster_names:
                continue
            hint = sorted(r for r in roster_names if _normalize(r) == _normalize(name))
            orphans.append(
                {"subject": name, **classify_log(log_path), "possible_roster_alias": hint}
            )

    def _count(items: list[dict[str, Any]], pred: Any) -> int:
        return sum(1 for s in items if pred(s))

    summary = {
        "providers": len(subjects),
        "registered": _count(subjects, lambda s: s["registered"]),
        "unregistered": _count(subjects, lambda s: not s["registered"]),
        "actuated": _count(subjects, lambda s: s["standing"] == ACTUATED),
        "not_run": _count(subjects, lambda s: s["standing"] == NOT_RUN),
        "named_gap": _count(subjects, lambda s: s["standing"] in GAP_STANDINGS),
        "gap_breakdown": {
            g: _count(subjects, lambda s, g=g: s["standing"] == g)
            for g in GAP_STANDINGS
            if _count(subjects, lambda s, g=g: s["standing"] == g)
        },
        "has_test_file": _count(subjects, lambda s: s["has_test_file"]),
        "test_file_but_not_actuated": _count(
            subjects, lambda s: s["has_test_file"] and s["standing"] != ACTUATED
        ),
        "orphan_logs": len(orphans),
        "orphan_actuated": _count(orphans, lambda s: s["standing"] == ACTUATED),
    }
    return {"summary": summary, "subjects": subjects, "orphan_logs": orphans}


def git_head_short(repo_root: Path = REPO_ROOT) -> str:
    try:
        return subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def render_markdown(census: dict[str, Any], *, command: str, head: str) -> str:
    s = census["summary"]
    lines = [
        "# GymAct standing census",
        "",
        f"- Command: `{command}`",
        f"- Tree git HEAD: `{head}`",
        "",
        "**pytest-passing != actuated.** A `tests/test_<gym>*.py` file (or a green run of it) is",
        "a claim about `request accepted`. Only a real, schema-valid, conformant-replay log with",
        "a real `act` event carrying `solved=True` counts as ACTUATED here, derived directly from",
        "`reports/ocel/<subject>/episode.ocel.json` per `.claude/rules/ocel-standing.md`.",
        "This census is a measurement of committed logs; it is not a release-standing claim and",
        "it does not re-run any episode.",
        "",
        "## Headline",
        "",
        f"- Providers in roster: **{s['providers']}** "
        f"({s['registered']} registered builtins, "
        f"{s['unregistered']} unregistered Provider classes)",
        f"- ACTUATED: **{s['actuated']}**",
        f"- NOT_RUN (no log): **{s['not_run']}**",
        f"- Named gap (log exists, not ACTUATED): **{s['named_gap']}** {s['gap_breakdown']}",
        f"- Have a test file: {s['has_test_file']} "
        f"(of which not ACTUATED: {s['test_file_but_not_actuated']})",
        f"- Logs under reports/ocel matching no roster subject: {s['orphan_logs']} "
        f"({s['orphan_actuated']} ACTUATED)",
        "",
        "## Roster",
        "",
        "| subject | registered | provider class | OCEL standing | schema | conformant | "
        "act / solved | test file | detail |",
        "|---|---|---|---|---|---|---|---|---|",
    ]

    def _cell(value: Any) -> str:
        return "-" if value is None else str(value)

    def _row(item: dict[str, Any], *, registered: Any, cls: Any) -> str:
        act = (
            "-"
            if item["act_events"] is None
            else f"{item['act_events']} / {item['solved_act_events']}"
        )
        tests = ", ".join(item.get("test_files", [])) or ("-" if "test_files" in item else "n/a")
        detail = str(item["detail"]).replace("|", "\\|").replace("\n", " ")[:140]
        return (
            f"| {item['subject']} | {registered} | {cls} | {item['standing']} | "
            f"{_cell(item['schema_valid'])} | {_cell(item['conformant'])} | {act} | "
            f"{tests} | {detail} |"
        )

    for item in census["subjects"]:
        lines.append(_row(item, registered=item["registered"], cls=item["provider_class"]))
    lines += ["", "## Logs matching no roster subject", ""]
    if census["orphan_logs"]:
        lines += [
            "| subject | OCEL standing | schema | conformant | act / solved | "
            "possible alias | detail |",
            "|---|---|---|---|---|---|---|",
        ]
        for item in census["orphan_logs"]:
            act = (
                "-"
                if item["act_events"] is None
                else f"{item['act_events']} / {item['solved_act_events']}"
            )
            lines.append(
                f"| {item['subject']} | {item['standing']} | {_cell(item['schema_valid'])} | "
                f"{_cell(item['conformant'])} | {act} | "
                f"{', '.join(item['possible_roster_alias']) or '-'} | "
                f"{str(item['detail']).replace('|', chr(92) + '|')[:140]} |"
            )
        lines += [
            "",
            "A possible alias is only a naming hint; it does not change the roster subject's",
            "classification (an exact directory-name match is required).",
        ]
    else:
        lines.append("None.")
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--json", action="store_true", help="emit JSON to stdout")
    parser.add_argument("--markdown", action="store_true", help="emit Markdown table to stdout")
    parser.add_argument("--reports-dir", type=Path, default=REPO_ROOT / "reports" / "ocel")
    parser.add_argument("--tests-dir", type=Path, default=REPO_ROOT / "tests")
    args = parser.parse_args(argv)
    if args.json == args.markdown:
        parser.error("choose exactly one of --json / --markdown")

    census = build_census(args.reports_dir, args.tests_dir)
    census["git_head"] = git_head_short()
    if args.json:
        print(json.dumps(census, indent=2, sort_keys=True))
    else:
        command = "python scripts/standing_census.py --markdown"
        print(render_markdown(census, command=command, head=census["git_head"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
