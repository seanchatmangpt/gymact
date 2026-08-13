#!/usr/bin/env python3
"""Run one real GymAct episode over `ResourceFlowProvider` -- a real, seeded,
bounded local environment (no network/Docker) -- and write a real OCEL 2.0
log at reports/ocel/resource-flow/episode.ocel.json.

Mirrors `scripts/run_switchboard_episode.py`'s shape. No authority gate.

The episode solves the seeded flow deterministically without ever touching
the irreversible `burn_catalyst` trap: repeatedly `mine` -> `refine` ->
`assemble` until `output >= target`, verified via
`gym.verify(..., {"solved": True})`.

Usage:
    uv run python scripts/run_resource_flow_episode.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from gymact import GymAct, MaterializationIntent
from gymact.gyms.resource_flow import ResourceFlowProvider
from gymact.models import ActuationIntent
from gymact.ocel import write_ocel_log

REPORTS_DIR = Path(__file__).parent.parent / "reports" / "ocel"

MINE = "urn:gymact:resource-flow:capability:mine"
REFINE = "urn:gymact:resource-flow:capability:refine"
ASSEMBLE = "urn:gymact:resource-flow:capability:assemble"

SEED = 0
CAPACITY = 8
TARGET = 3
MAX_STEPS = 100


async def run() -> None:
    gym = GymAct()
    gym.register_provider(ResourceFlowProvider())
    receipts = []
    log_path = REPORTS_DIR / "resource-flow" / "episode.ocel.json"

    materialization = await gym.materialize(
        MaterializationIntent(
            provider="resource-flow",
            config={"seed": SEED, "capacity": CAPACITY, "target": TARGET},
        )
    )
    receipts.append(materialization.receipt)
    if not materialization.accepted or materialization.episode is None:
        print(f"resource-flow: materialization refused: {materialization.receipt.reason}")
        log, digest = write_ocel_log(log_path, receipts)
        print(f"resource-flow: {len(log['events'])} events, sha256={digest}")
        return

    episode_id = materialization.episode.episode_id
    print(f"resource-flow: seed={SEED} capacity={CAPACITY} target={TARGET}")

    last_receipt = materialization.receipt
    try:
        for step in range(MAX_STEPS):
            observation = await gym.observe(episode_id)
            observed = observation.state
            if observed.get("output", 0) >= TARGET:
                break
            if observed.get("refined", 0) >= 1:
                result = await gym.act(ActuationIntent(episode_id=episode_id, capability=ASSEMBLE))
            elif observed.get("raw", 0) >= 1:
                result = await gym.act(ActuationIntent(episode_id=episode_id, capability=REFINE))
            else:
                result = await gym.act(ActuationIntent(episode_id=episode_id, capability=MINE))
            receipts.append(result.receipt)
            last_receipt = result.receipt

        verification = await gym.verify(episode_id, {"solved": True})
        print(f"resource-flow: steps_taken<= {step + 1} verify_solved_passed={verification.passed}")

        receipts.append(
            last_receipt.model_copy(update={"reason": f"solved={verification.passed}"})
        )
    finally:
        receipts.append(await gym.teardown(episode_id))

    log, digest = write_ocel_log(log_path, receipts)
    print(f"resource-flow: {len(log['events'])} events, sha256={digest}")


if __name__ == "__main__":
    asyncio.run(run())
