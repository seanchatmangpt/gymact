#!/usr/bin/env python3
"""Run one real, full 10-phase TOGAF ADM episode -- including a real Phase H
change-request loop-back and recovery -- end to end, and write a real OCEL
2.0 log at reports/ocel/togaf/episode.ocel.json.

The provider is compiled by `gymact.gyms.ontology_gym.OntologyDrivenProvider`
directly from `ggen/togaf-gym-pack/ontology.ttl`'s ten real `pplan:Plan`
task instances (see `gymact.gyms.togaf.build_togaf_provider`) -- this
script drives the generated topology, it does not hand-code any phase.

A successful `GymAct.act()` never sets `Receipt.reason` (a real, documented
kernel-level gap -- see the comment above `_ACT_REASON_KERNEL_GAP_SUBJECTS`
in tests/test_ocel_standing.py), so the real, independently observed
goal_reached truth is attached via `model_copy` onto a copy of the final
recovery act's receipt before persisting -- the same pattern
scripts/discover_and_actuate.py already established for `solved`.

Usage:
    uv run python scripts/run_togaf_episode.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from gymact import GymAct, MaterializationIntent
from gymact.gyms.ontology_gym import TieredAuthorityResolver, capability_iri
from gymact.gyms.togaf import build_togaf_provider
from gymact.models import ActuationIntent
from gymact.ocel import write_ocel_log

REPORTS_DIR = Path(__file__).parent.parent / "reports" / "ocel"
STANDARD_REF = "urn:gymact:authority:togaf-episode-standard"
GOVERNANCE_REF = "urn:gymact:authority:togaf-episode-governance"


async def run() -> None:
    provider = build_togaf_provider()
    resolver = TieredAuthorityResolver(
        elevated_capabilities=provider.elevated_capability_iris(),
        standard_ref=STANDARD_REF,
        elevated_ref=GOVERNANCE_REF,
    )
    gym = GymAct(authority_resolver=resolver)
    gym.register_provider(provider)
    receipts = []
    log_path = REPORTS_DIR / "togaf" / "episode.ocel.json"

    materialization = await gym.materialize(
        MaterializationIntent(provider="togaf", config={})
    )
    receipts.append(materialization.receipt)
    if not materialization.accepted or materialization.episode is None:
        print(f"togaf: materialization refused: {materialization.receipt.reason}")
        log, digest = write_ocel_log(log_path, receipts)
        print(f"togaf: {len(log['events'])} events, sha256={digest}")
        return

    episode_id = materialization.episode.episode_id

    async def act_one(*, iri: str, subject: str | None, ref: str) -> bool:
        payload = {"subject": subject} if subject is not None else {}
        result = await gym.act(
            ActuationIntent(
                episode_id=episode_id, capability=iri, payload=payload, authority_ref=ref
            )
        )
        receipts.append(result.receipt)
        if not result.accepted:
            print(f"togaf: act refused: {iri} subject={subject}: {result.receipt.reason}")
        return result.accepted

    tasks = provider.tasks()
    for task in tasks:
        ref = GOVERNANCE_REF if task.family in provider.elevated_task_families else STANDARD_REF
        iri = capability_iri(provider_name="togaf", task=task)
        if len(task.subjects) == 1:
            if not await act_one(iri=iri, subject=None, ref=ref):
                receipts.append(await gym.teardown(episode_id, authority_ref=GOVERNANCE_REF))
                log, digest = write_ocel_log(log_path, receipts)
                print(f"togaf: {len(log['events'])} events, sha256={digest}")
                return
        else:
            for subject in task.subjects:
                if not await act_one(iri=iri, subject=subject, ref=ref):
                    receipts.append(
                        await gym.teardown(episode_id, authority_ref=GOVERNANCE_REF)
                    )
                    log, digest = write_ocel_log(log_path, receipts)
                    print(f"togaf: {len(log['events'])} events, sha256={digest}")
                    return

    # Phase H just cleared Requirements Management's facts as a real side
    # effect (task_family "change" resets task_family "requirements", per
    # gymact/gyms/togaf.py's configuration) -- recover by resubmitting them.
    requirements_task = tasks[1]
    assert requirements_task.family == "requirements"
    requirements_iri = capability_iri(provider_name="togaf", task=requirements_task)
    recovery_accepted = True
    for subject in requirements_task.subjects:
        recovery_accepted = await act_one(iri=requirements_iri, subject=subject, ref=STANDARD_REF)
        if not recovery_accepted:
            break

    if not recovery_accepted:
        receipts.append(await gym.teardown(episode_id, authority_ref=GOVERNANCE_REF))
        log, digest = write_ocel_log(log_path, receipts)
        print(f"togaf: {len(log['events'])} events, sha256={digest}")
        return

    verification = await gym.verify(episode_id, {"goal_reached": True})
    print(f"togaf: verify_passed={verification.passed}")

    receipt_with_solved = receipts.pop().model_copy(
        update={"reason": f"solved={verification.passed}"}
    )
    receipts.append(receipt_with_solved)

    receipts.append(await gym.teardown(episode_id, authority_ref=GOVERNANCE_REF))

    log, digest = write_ocel_log(log_path, receipts)
    print(f"togaf: {len(log['events'])} events, sha256={digest}")


if __name__ == "__main__":
    asyncio.run(run())
