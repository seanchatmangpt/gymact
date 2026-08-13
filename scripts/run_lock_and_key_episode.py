#!/usr/bin/env python3
"""Run one real GymAct episode over `LockAndKeyProvider` -- a real, seeded,
bounded local environment (no network/Docker) -- and write a real OCEL 2.0
log at reports/ocel/lock-and-key/episode.ocel.json.

Mirrors `scripts/run_switchboard_episode.py`'s shape. No authority gate
(`materialization_requires_authority = False`, environment constructed with
`requires_authority=False`).

The episode solves the seeded lock chain for real: for each of `depth`
locks, `pick_key` the environment's own `required_key()` oracle value
(the same helper `tests/test_lock_and_key.py` uses -- a legitimate
test/episode oracle, not the agent-facing hidden state), `open_lock`, then
`drop_key`, verified via `gym.verify(..., {"solved": True})` at the end.

Usage:
    uv run python scripts/run_lock_and_key_episode.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from gymact import GymAct, MaterializationIntent
from gymact.gyms.lock_and_key import LockAndKeyEnvironment, LockAndKeyProvider
from gymact.models import ActuationIntent
from gymact.ocel import write_ocel_log

REPORTS_DIR = Path(__file__).parent.parent / "reports" / "ocel"

PICK = "urn:gymact:lock-and-key:capability:pick_key"
DROP = "urn:gymact:lock-and-key:capability:drop_key"
OPEN = "urn:gymact:lock-and-key:capability:open_lock"

SEED = 0
DEPTH = 4


async def run() -> None:
    gym = GymAct()
    gym.register_provider(LockAndKeyProvider())
    receipts = []
    log_path = REPORTS_DIR / "lock-and-key" / "episode.ocel.json"

    materialization = await gym.materialize(
        MaterializationIntent(provider="lock-and-key", config={"seed": SEED, "depth": DEPTH})
    )
    receipts.append(materialization.receipt)
    if not materialization.accepted or materialization.episode is None:
        print(f"lock-and-key: materialization refused: {materialization.receipt.reason}")
        log, digest = write_ocel_log(log_path, receipts)
        print(f"lock-and-key: {len(log['events'])} events, sha256={digest}")
        return

    episode_id = materialization.episode.episode_id
    env: LockAndKeyEnvironment = gym._episodes[episode_id].environment
    print(f"lock-and-key: seed={SEED} depth={DEPTH}")

    last_receipt = materialization.receipt
    try:
        for lock_index in range(DEPTH):
            key = env.required_key()
            pick_result = await gym.act(
                ActuationIntent(episode_id=episode_id, capability=PICK, payload={"key": key})
            )
            receipts.append(pick_result.receipt)
            open_result = await gym.act(
                ActuationIntent(episode_id=episode_id, capability=OPEN)
            )
            receipts.append(open_result.receipt)
            last_receipt = open_result.receipt
            print(
                f"lock-and-key: lock {lock_index}: key={key} pick_accepted={pick_result.accepted} "
                f"open_accepted={open_result.accepted}"
            )
            drop_result = await gym.act(
                ActuationIntent(episode_id=episode_id, capability=DROP)
            )
            receipts.append(drop_result.receipt)

        verification = await gym.verify(episode_id, {"solved": True})
        print(f"lock-and-key: verify_solved_passed={verification.passed}")

        receipts.append(
            last_receipt.model_copy(update={"reason": f"solved={verification.passed}"})
        )
    finally:
        receipts.append(await gym.teardown(episode_id))

    log, digest = write_ocel_log(log_path, receipts)
    print(f"lock-and-key: {len(log['events'])} events, sha256={digest}")


if __name__ == "__main__":
    asyncio.run(run())
