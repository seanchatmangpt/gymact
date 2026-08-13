#!/usr/bin/env python3
"""Run one real GymAct episode over `K8sResourceProvider` -- a real,
read-only, in-process gym over the bundled Kubernetes OpenAPI resource-kind
snapshot (`k8s_openapi_snapshot.json`) -- and write a real OCEL 2.0 log at
reports/ocel/k8s-resources/episode.ocel.json.

All three capabilities here are `Consequence.READ`. Per `kernel.py`'s
`READ_CAPABILITY_IS_NOT_ACTUATION` refusal, `gym.act()` refuses them; the
real, symmetric counterpart is `gym.read()` (`kernel.py:535`), which invokes
the capability directly against the environment's real, already-loaded
state and -- by its own docstring -- carries no `Receipt`/authority path,
matching every real READ-only gym's `requires_authority=False` convention
(same structural reality noted for `cloud_topology`'s READ-only capabilities
in the round-3 plan, RPN 150: a purely-informational query has no
consequence to gate or record as an `act` event). The real OCEL evidence
this episode records is therefore `materialize` -> `observe` -> `verify` ->
`teardown`, with every `gym.read()` call's real result printed to stdout as
the read-path proof (not fabricated -- see the captured command output).

Usage:
    uv run python scripts/run_k8s_resources_episode.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from gymact import GymAct, MaterializationIntent
from gymact.gyms.k8s_resource_gym import K8sResourceProvider
from gymact.ocel import write_ocel_log

REPORTS_DIR = Path(__file__).parent.parent / "reports" / "ocel"

LIST_KINDS = "urn:gymact:k8s-resource:capability:list_resource_kinds"
REQUIRED_FIELDS = "urn:gymact:k8s-resource:capability:required_fields_for_kind"
PROVIDERS = "urn:gymact:k8s-resource:capability:providers_offering_kind"


async def run() -> None:
    gym = GymAct()
    gym.register_provider(K8sResourceProvider())
    receipts = []
    log_path = REPORTS_DIR / "k8s-resources" / "episode.ocel.json"

    materialization = await gym.materialize(
        MaterializationIntent(provider="k8s-resource", config={})
    )
    receipts.append(materialization.receipt)
    if not materialization.accepted or materialization.episode is None:
        print(f"k8s-resources: materialization refused: {materialization.receipt.reason}")
        log, digest = write_ocel_log(log_path, receipts)
        print(f"k8s-resources: {len(log['events'])} events, sha256={digest}")
        return

    episode_id = materialization.episode.episode_id
    try:
        observation = await gym.observe(episode_id)
        print(f"k8s-resources: observe state={observation.state}")

        kinds = await gym.read(episode_id, LIST_KINDS, {})
        print(f"k8s-resources: read(list_resource_kinds) = {kinds['result']}")

        for kind in kinds["result"]:
            fields = await gym.read(episode_id, REQUIRED_FIELDS, {"kind": kind})
            print(f"k8s-resources: read(required_fields_for_kind, {kind}) = {fields['result']}")

            providers = await gym.read(episode_id, PROVIDERS, {"kind": kind})
            print(f"k8s-resources: read(providers_offering_kind, {kind}) = {providers['result']}")

        verification = await gym.verify(episode_id, {})
        print(f"k8s-resources: verify_passed={verification.passed}")
    finally:
        receipts.append(await gym.teardown(episode_id))

    log, digest = write_ocel_log(log_path, receipts)
    print(f"k8s-resources: {len(log['events'])} events, sha256={digest}")


if __name__ == "__main__":
    asyncio.run(run())
