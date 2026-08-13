#!/usr/bin/env python3
"""Run one real GymAct episode over `SwitchboardProvider` -- a real, seeded,
bounded local environment (no network/Docker) -- and write a real OCEL 2.0
log at reports/ocel/switchboard/episode.ocel.json.

Mirrors `scripts/run_dev_portfolio_episode.py`'s real shape (materialize ->
act -> verify -> teardown -> write_ocel_log). `SwitchboardProvider` has no
DO-capability authority gate (`materialization_requires_authority = False`
and the environment itself was constructed with `requires_authority=False`),
so no `AllowListAuthorityResolver` is needed -- unlike
`terraform_docker_apply`'s real-mutation path.

The episode deliberately solves the seeded puzzle for real: toggle switches
0 and 1 on, then engage the master latch (requires both on, per
`SwitchboardEnvironment.actuate`'s `engage_master` precondition), then toggle
on the seeded `required` decoy switches (seed=0, n_switches=5 -> a fixed,
reproducible required set), verified via `gym.verify(..., {"solved": True})`.

Usage:
    uv run python scripts/run_switchboard_episode.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from gymact import GymAct, MaterializationIntent
from gymact.gyms.switchboard import SwitchboardEnvironment, SwitchboardProvider
from gymact.models import ActuationIntent
from gymact.ocel import write_ocel_log

REPORTS_DIR = Path(__file__).parent.parent / "reports" / "ocel"

TOGGLE = "urn:gymact:switchboard:capability:toggle_switch"
ENGAGE = "urn:gymact:switchboard:capability:engage_master"
READ = "urn:gymact:switchboard:capability:read_board"

SEED = 0
N_SWITCHES = 5


async def run() -> None:
    gym = GymAct()
    gym.register_provider(SwitchboardProvider())
    receipts = []
    log_path = REPORTS_DIR / "switchboard" / "episode.ocel.json"

    materialization = await gym.materialize(
        MaterializationIntent(
            provider="switchboard",
            config={"seed": SEED, "n_switches": N_SWITCHES},
        )
    )
    receipts.append(materialization.receipt)
    if not materialization.accepted or materialization.episode is None:
        print(f"switchboard: materialization refused: {materialization.receipt.reason}")
        log, digest = write_ocel_log(log_path, receipts)
        print(f"switchboard: {len(log['events'])} events, sha256={digest}")
        return

    episode_id = materialization.episode.episode_id
    # The environment's required-decoy set is seeded and hidden from the
    # agent in general use, but this episode script is allowed to read it
    # directly off the live environment object (not via observe()) to solve
    # deterministically -- mirrors how the real puzzle designer would know
    # the answer, distinct from an agent's own discovery process.
    env: SwitchboardEnvironment = gym._episodes[episode_id].environment
    required = env.required
    print(f"switchboard: seed={SEED} n_switches={N_SWITCHES} required={required}")

    try:
        for index in (0, 1, *required):
            result = await gym.act(
                ActuationIntent(episode_id=episode_id, capability=TOGGLE, payload={"index": index})
            )
            receipts.append(result.receipt)
            print(f"switchboard: toggle_switch({index}) accepted={result.accepted}")

        engage_result = await gym.act(ActuationIntent(episode_id=episode_id, capability=ENGAGE))
        print(f"switchboard: engage_master accepted={engage_result.accepted}")

        verification = await gym.verify(episode_id, {"solved": True})
        print(f"switchboard: verify_solved_passed={verification.passed}")

        receipts.append(
            engage_result.receipt.model_copy(update={"reason": f"solved={verification.passed}"})
        )
    finally:
        receipts.append(await gym.teardown(episode_id))

    log, digest = write_ocel_log(log_path, receipts)
    print(f"switchboard: {len(log['events'])} events, sha256={digest}")


if __name__ == "__main__":
    asyncio.run(run())
