#!/usr/bin/env python3
"""Run one real TOGAF Preliminary/Requirements Management episode end to end
and write a real OCEL 2.0 log at reports/ocel/togaf/episode.ocel.json.

This is the v26.8.11 M1 driver from
docs/prd/v26.8.11-togaf-fortune5-adm-gym.md: register the real
`TogafProvider`, materialize, actuate both real capabilities in order
(establish -> submit all four requirement subjects), independently verify
`goal_reached`, teardown, and persist the log -- the same
materialize/act/verify/teardown/write_ocel_log sequence
`scripts/discover_and_actuate.py` and `tests/test_ocel.py`'s
`_run_real_counter_episode()` already use for other gyms.

A successful `GymAct.act()` never sets `Receipt.reason` (a real, documented
kernel-level gap -- see the comment above `_ACT_REASON_KERNEL_GAP_SUBJECTS`
in tests/test_ocel_standing.py), so no real act event could otherwise carry
`solved=True` evidence. This script follows the same fix
`discover_and_actuate.py` already applies: attach the real, independently
observed `goal_reached` truth onto a *copy* of the final act receipt's
`reason` field before appending it to the log, so the OCEL log itself -- not
this script's stdout -- carries that evidence.

Usage:
    uv run python scripts/run_togaf_episode.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from gymact import AllowListAuthorityResolver, GymAct, MaterializationIntent
from gymact.gyms.togaf import (
    CAPABILITY_ESTABLISH,
    CAPABILITY_SUBMIT,
    REQUIREMENT_SUBJECTS,
    TogafProvider,
)
from gymact.models import ActuationIntent
from gymact.ocel import write_ocel_log

REPORTS_DIR = Path(__file__).parent.parent / "reports" / "ocel"
AUTHORITY = "urn:gymact:authority:togaf-m1-episode"


async def run() -> None:
    gym = GymAct(authority_resolver=AllowListAuthorityResolver({AUTHORITY}))
    gym.register_provider(TogafProvider())
    receipts = []

    materialization = await gym.materialize(
        MaterializationIntent(provider="togaf", config={})
    )
    receipts.append(materialization.receipt)
    if not materialization.accepted or materialization.episode is None:
        print(f"togaf: materialization refused: {materialization.receipt.reason}")
        log, digest = write_ocel_log(REPORTS_DIR / "togaf" / "episode.ocel.json", receipts)
        print(f"togaf: {len(log['events'])} events, sha256={digest}")
        return

    episode_id = materialization.episode.episode_id

    establish_result = await gym.act(
        ActuationIntent(
            episode_id=episode_id,
            capability=CAPABILITY_ESTABLISH,
            authority_ref=AUTHORITY,
        )
    )
    receipts.append(establish_result.receipt)
    if not establish_result.accepted:
        print(f"togaf: establish refused: {establish_result.receipt.reason}")
        receipts.append(await gym.teardown(episode_id, authority_ref=AUTHORITY))
        log, digest = write_ocel_log(REPORTS_DIR / "togaf" / "episode.ocel.json", receipts)
        print(f"togaf: {len(log['events'])} events, sha256={digest}")
        return

    final_submit_result = None
    for requirement in REQUIREMENT_SUBJECTS:
        submit_result = await gym.act(
            ActuationIntent(
                episode_id=episode_id,
                capability=CAPABILITY_SUBMIT,
                payload={"requirement": requirement},
                authority_ref=AUTHORITY,
            )
        )
        final_submit_result = submit_result
        if requirement != REQUIREMENT_SUBJECTS[-1]:
            receipts.append(submit_result.receipt)
        if not submit_result.accepted:
            print(f"togaf: submit({requirement}) refused: {submit_result.receipt.reason}")
            receipts.append(await gym.teardown(episode_id, authority_ref=AUTHORITY))
            log, digest = write_ocel_log(REPORTS_DIR / "togaf" / "episode.ocel.json", receipts)
            print(f"togaf: {len(log['events'])} events, sha256={digest}")
            return

    verification = await gym.verify(episode_id, {"goal_reached": True})
    print(f"togaf: verify_passed={verification.passed}")

    # Attach the real, independently observed goal_reached truth onto a copy
    # of the final act receipt, the same pattern discover_and_actuate.py uses
    # for `solved` -- real evidence, embedded on the OCEL log's own act event,
    # not narrated only in this script's stdout.
    assert final_submit_result is not None
    receipt_with_solved = final_submit_result.receipt.model_copy(
        update={"reason": f"solved={verification.passed}"}
    )
    receipts.append(receipt_with_solved)

    receipts.append(await gym.teardown(episode_id, authority_ref=AUTHORITY))

    log, digest = write_ocel_log(REPORTS_DIR / "togaf" / "episode.ocel.json", receipts)
    print(f"togaf: {len(log['events'])} events, sha256={digest}")


if __name__ == "__main__":
    asyncio.run(run())
