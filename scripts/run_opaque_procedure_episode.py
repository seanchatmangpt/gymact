#!/usr/bin/env python3
"""Run one real GymAct discovery episode over `OpaqueProcedureProvider` --
materialize -> discover (real BFS probing, no cheating on the hidden step
order) -> replay -> real OCEL 2.0 log -- and persist it to
reports/ocel/opaque-procedure/episode.ocel.json.

This is not a new capability: `tests/test_discovery_probes.py`'s
`test_opaque_probe_discovery_is_brce_receipted_and_replayable` already
proves this exact materialize->discover->replay->schema-valid-OCEL path
in-memory (`replay.ocel_log`, validated via `validate_ocel_log`). This
script reuses that same real logic and collaborators (`DiscoveryProbeRunner`,
`ProductionGymAct`, real BFS discovery over the hidden action graph) and
adds the one missing step: writing the real, already-produced log to disk
so it becomes durable, committed evidence discoverable by
`tests/test_ocel_standing.py`, mirroring every other `run_<name>_episode.py`
script's contract.

Usage:
    uv run python scripts/run_opaque_procedure_episode.py
"""

from __future__ import annotations

import asyncio
import json
import sys
from collections import deque
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from gymact.discovery import DiscoveryProbeRunner
from gymact.gyms.opaque_procedure import OpaqueProcedureProvider
from gymact.models import Standing
from gymact.ocel import validate_ocel_log
from gymact.runtime import ProductionGymAct

REPORTS_DIR = Path(__file__).parent.parent / "reports" / "ocel"

# Same held-out puzzle `tests/test_discovery_probes.py` uses -- a real,
# reproducible 2-step hidden action graph (start -> middle -> done). The
# agent-facing action IRIs never reveal "begin-human-readable"/
# "finish-human-readable"; discovery must find the order by real BFS
# probing, not by reading these IDs.
PRIVATE = {
    "subject": "opaque-procedure-episode",
    "initial_facts": ["start"],
    "goal_facts": ["done"],
    "steps": [
        {
            "id": "finish-human-readable",
            "preconditions": ["middle"],
            "establishes": ["done"],
        },
        {
            "id": "begin-human-readable",
            "preconditions": ["start"],
            "establishes": ["middle"],
        },
    ],
}


async def _discover(runner: DiscoveryProbeRunner) -> tuple[str, ...]:
    initial, actions = await runner.challenge()
    queue = deque([(frozenset(initial), ())])
    seen = {frozenset(initial)}
    while queue:
        _state, prefix = queue.popleft()
        for action in actions:
            evidence = await runner.probe(prefix=prefix, action_id=action)
            if not evidence.accepted:
                assert evidence.standing in {
                    Standing.BLOCKED,
                    Standing.REFUSED,
                    Standing.UNSUPPORTED,
                }
                continue
            after = frozenset(evidence.after_facts)
            candidate = prefix + (action,)
            if "done" in after:
                return candidate
            if after not in seen:
                seen.add(after)
                queue.append((after, candidate))
    raise AssertionError("goal was not discovered")


async def run() -> None:
    runtime = ProductionGymAct(validate_profile=False)
    runtime.register_provider(OpaqueProcedureProvider())
    runner = DiscoveryProbeRunner(
        runtime,
        provider="opaque-procedure",
        subject="opaque-procedure-episode",
        private_config=PRIVATE,
    )

    initial, actions = await runner.challenge()
    print(f"opaque-procedure: initial_facts={initial} action_count={len(actions)}")

    plan = await _discover(runner)
    print(f"opaque-procedure: discovered_plan_length={len(plan)}")

    replay = await runner.replay(plan=plan)
    print(
        f"opaque-procedure: replay standing={replay.standing} "
        f"goal_reached={replay.goal_reached} final_facts={replay.final_facts}"
    )
    assert replay.standing is Standing.ALIVE
    assert replay.goal_reached is True

    validate_ocel_log(replay.ocel_log)

    log_path = REPORTS_DIR / "opaque-procedure" / "episode.ocel.json"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    canonical = json.dumps(replay.ocel_log, sort_keys=True, separators=(",", ":"))
    log_path.write_text(canonical, encoding="utf-8")

    import hashlib

    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    print(f"opaque-procedure: {len(replay.ocel_log['events'])} events, sha256={digest}")
    print(f"opaque-procedure: written to {log_path}")


if __name__ == "__main__":
    asyncio.run(run())
