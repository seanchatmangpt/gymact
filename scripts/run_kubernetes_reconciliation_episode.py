#!/usr/bin/env python3
"""Run one real GymAct episode over `KubernetesReconciliationProvider` -- a
real Pod on a real local Kubernetes cluster (kind/k3d/colima --kubernetes),
`scale_restart` forcing a real delete+reapply reschedule -- and write a real
OCEL 2.0 log at reports/ocel/kubernetes-reconciliation/episode.ocel.json.

Mirrors `scripts/run_terraform_docker_apply_episode.py`'s shape
(materialize -> verify -> act(DO) -> verify -> teardown ->
write_ocel_log), which itself mirrors `scripts/run_dev_portfolio_episode.py`
and `scripts/run_togaf_episode.py`. `KubernetesReconciliationEnvironment`
materializes its real Pod inside `__init__` (via a real `kubectl apply -f -`
subprocess call), so the episode's first real proof point is the initial
`verify(episode_id, {"running": True})` -- confirming the pod actually
reached `Running` on the real cluster, not just that `kubectl apply`
returned 0.

Per `gymact.standing.require_standing`, this script refuses to run (loud,
not silent) if no real Kubernetes cluster is reachable on the current
kubeconfig context -- matching `tests/test_kubernetes_reconciliation.py`'s
own gate.

Honest status as of the 2026-08-13 FMEA+RCA closure session that wrote this
script: this file is real, complete code exercising the real provider
end-to-end, but it was NOT executed this session. The sandbox's local `kind`
cluster (`gymact-test`) was found already dead (every system pod, including
`kube-apiserver`, in `Exited` state -- pre-existing infra rot, not caused by
this script) and could not be recreated: `kind create cluster` failed
pulling `kindest/node:v1.34.0` because this sandbox has no outbound network
egress to `registry-1.docker.io`. Re-run this script for real once a
reachable local cluster exists (`kind create cluster` from a machine/session
with real network access, or `colima start --kubernetes` once its dnsmasq
setup issue -- also observed this session -- is resolved) to produce the
real OCEL log this episode is designed to write.

Usage:
    uv run python scripts/run_kubernetes_reconciliation_episode.py
"""

from __future__ import annotations

import asyncio
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from gymact import AllowListAuthorityResolver, GymAct, MaterializationIntent
from gymact.gyms.kubernetes_reconciliation import KubernetesReconciliationProvider
from gymact.models import ActuationIntent
from gymact.ocel import write_ocel_log
from gymact.standing import require_standing

REPORTS_DIR = Path(__file__).parent.parent / "reports" / "ocel"

SCALE_RESTART = "urn:gymact:kubernetes-reconciliation:capability:scale_restart"
AUTHORITY = "urn:gymact:kubernetes-reconciliation-episode:authority"


def _real_cluster_reachable() -> bool:
    if shutil.which("kubectl") is None:
        return False
    try:
        result = subprocess.run(
            ["kubectl", "cluster-info"], capture_output=True, text=True, timeout=10.0, check=False
        )
        return result.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


require_standing(
    "LOCAL_GYM:kubernetes-reconciliation",
    available=_real_cluster_reachable(),
    reason="no reachable Kubernetes cluster on the current kubeconfig context "
    "(start one locally: `kind create cluster`, `k3d cluster create`, or "
    "`colima start --kubernetes`)",
)


async def run() -> None:
    gym = GymAct(authority_resolver=AllowListAuthorityResolver({AUTHORITY}))
    gym.register_provider(KubernetesReconciliationProvider())
    receipts = []
    log_path = REPORTS_DIR / "kubernetes-reconciliation" / "episode.ocel.json"

    materialization = await gym.materialize(
        MaterializationIntent(provider="kubernetes-reconciliation", config={})
    )
    receipts.append(materialization.receipt)
    if not materialization.accepted or materialization.episode is None:
        print(f"kubernetes-reconciliation: materialization refused: {materialization.receipt.reason}")
        log, digest = write_ocel_log(log_path, receipts)
        print(f"kubernetes-reconciliation: {len(log['events'])} events, sha256={digest}")
        return

    episode_id = materialization.episode.episode_id

    try:
        verification = await gym.verify(episode_id, {"running": True})
        print(f"kubernetes-reconciliation: verify_initial_running_passed={verification.passed}")

        result = await gym.act(
            ActuationIntent(episode_id=episode_id, capability=SCALE_RESTART, authority_ref=AUTHORITY)
        )
        print(f"kubernetes-reconciliation: scale_restart accepted={result.accepted}")

        verification_after = await gym.verify(episode_id, {"running": True})
        print(f"kubernetes-reconciliation: verify_after_restart_passed={verification_after.passed}")

        receipts.append(
            result.receipt.model_copy(
                update={"reason": f"solved={verification_after.passed}"}
            )
        )
    finally:
        receipts.append(await gym.teardown(episode_id, authority_ref=AUTHORITY))

    log, digest = write_ocel_log(log_path, receipts)
    print(f"kubernetes-reconciliation: {len(log['events'])} events, sha256={digest}")


if __name__ == "__main__":
    asyncio.run(run())
