#!/usr/bin/env python3
"""Derive GymAct actuation standing PURELY from OCEL 2.0 log files -- never
from anything the driver script printed or anything narrated in chat.

For each `.ocel.json` file under a given directory:
  1. Real jsonschema.validate against the real official OCEL 2.0 schema.
  2. Extract `events[].type` (sorted by real `time`) -- no access to the
     driver's in-memory receipts, no access to its stdout.
  3. Re-run `gymact.process.ConformanceChecker` fresh on that extracted
     sequence.
  4. Standing is GYMACT_ACTUATED only if: the log is schema-valid, replay is
     conformant, AND at least one `act` event's `standing` attribute is
     "ALIVE" with "solved":"True" recorded via a `verify` event's attributes
     -- otherwise the real, lower, real reason is reported (BLOCKED /
     PARTIAL / SCHEMA_INVALID / NONCONFORMANT).

This script is the sole source of standing claims for this batch; its stdout
IS the report, not a summary of it.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from jsonschema.exceptions import ValidationError  # noqa: E402

from gymact.models import Operation  # noqa: E402
from gymact.ocel import validate_ocel_log  # noqa: E402
from gymact.process import ConformanceChecker  # noqa: E402


def _derive_one(log_path: Path) -> dict:
    raw_bytes = log_path.read_bytes()
    digest = hashlib.sha256(raw_bytes).hexdigest()
    log = json.loads(raw_bytes)

    try:
        validate_ocel_log(log)
    except ValidationError as exc:
        return {
            "subject": log_path.parent.name,
            "path": str(log_path),
            "digest": digest,
            "standing": "SCHEMA_INVALID",
            "reason": str(exc.message),
        }

    events_by_time = sorted(log["events"], key=lambda e: e["time"])
    try:
        operations = [Operation(e["type"]) for e in events_by_time]
    except ValueError as exc:
        return {
            "subject": log_path.parent.name,
            "path": str(log_path),
            "digest": digest,
            "standing": "UNKNOWN_OPERATION",
            "reason": str(exc),
        }

    conformance = ConformanceChecker().check(operations)
    if not conformance.conformant:
        return {
            "subject": log_path.parent.name,
            "path": str(log_path),
            "digest": digest,
            "standing": "NONCONFORMANT",
            "reason": "; ".join(d.reason for d in conformance.deviations),
        }

    act_events = [e for e in events_by_time if e["type"] == "act"]

    def _reason_of(event: dict) -> str:
        for a in event["attributes"]:
            if a["name"] == "reason":
                return a["value"]
        return ""

    # `standing == "ALIVE"` on an act event means only that the actuation
    # mechanism executed without raising -- a failed `import` inside a
    # successfully-run subprocess is still ALIVE at that level. The real
    # task-solved truth is `solved=True` embedded in the reason field by the
    # driver (gymact/discover_and_actuate.py) from the actual observed
    # subprocess result -- that, not receipt.standing alone, is what
    # GYMACT_ACTUATED requires here.
    act_solved = any("solved=True" in _reason_of(e) for e in act_events)

    if not act_events:
        standing = "BOOTSTRAPS"
        reason = "conformant materialize/teardown only -- no act event present"
    elif not act_solved:
        standing = "BLOCKED"
        reasons = [_reason_of(e) for e in act_events if _reason_of(e)]
        reason = (
            "; ".join(reasons)
            if reasons
            else "act event(s) present but none carry solved=True evidence"
        )
    else:
        standing = "GYMACT_ACTUATED"
        reason = f"{len(act_events)} real act event(s) with solved=True evidence, conformant replay"

    return {
        "subject": log_path.parent.name,
        "path": str(log_path),
        "digest": digest,
        "standing": standing,
        "reason": reason,
    }


def main() -> None:
    if len(sys.argv) < 2:
        print("usage: ocel_standing.py <ocel_reports_dir>", file=sys.stderr)
        sys.exit(2)

    root = Path(sys.argv[1])
    log_paths = sorted(root.glob("*/episode.ocel.json"))
    if not log_paths:
        print(f"no OCEL logs found under {root}", file=sys.stderr)
        sys.exit(1)

    results = [_derive_one(p) for p in log_paths]

    for r in results:
        print(
            f"{r['subject']:20s} standing={r['standing']:18s} "
            f"digest={r['digest']} reason={r['reason']}"
        )

    counts: dict[str, int] = {}
    for r in results:
        counts[r["standing"]] = counts.get(r["standing"], 0) + 1
    print("---")
    print(f"total={len(results)} " + " ".join(f"{k}={v}" for k, v in sorted(counts.items())))


if __name__ == "__main__":
    main()
