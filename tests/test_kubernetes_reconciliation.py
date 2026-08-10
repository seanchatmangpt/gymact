"""Chicago-style: a real GymAct episode driven against a real local
Kubernetes cluster (`kind`/`k3d`/colima `--kubernetes`) via real `kubectl`
subprocess calls -- not simulated.

This closes the gap named in this session's audit: zero Kubernetes code
anywhere in gymact, and specifically that `verify()` must poll real
cluster-observed state (`kubectl get pod ... -o json`'s `.status.phase`),
not just trust `kubectl apply`'s exit code.

Per `gymact.standing.require_standing`, the real thing is the default: if
no real Kubernetes cluster is reachable via the current kubeconfig context,
this module FAILS unless the run explicitly sets
`GYMACT_ALLOW_DEGRADED_STANDINGS` to include
"LOCAL_GYM:kubernetes-reconciliation" (or "*") -- a skip here is something a
run must opt into, never something it silently gets. Matches
`test_cube_container_counter.py`'s contract.
"""

from __future__ import annotations

import shutil
import subprocess

from gymact.standing import require_standing


def _kubectl_available() -> bool:
    return shutil.which("kubectl") is not None


def _real_cluster_reachable() -> bool:
    if not _kubectl_available():
        return False
    try:
        result = subprocess.run(
            ["kubectl", "cluster-info"],
            capture_output=True,
            text=True,
            timeout=10.0,
            check=False,
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

from gymact import AllowListAuthorityResolver, GymAct, MaterializationIntent  # noqa: E402
from gymact.gyms.kubernetes_reconciliation import KubernetesReconciliationProvider  # noqa: E402
from gymact.models import ActuationIntent, Operation, Standing  # noqa: E402
from gymact.ocel import receipts_to_ocel, validate_ocel_log  # noqa: E402
from gymact.process import ConformanceChecker  # noqa: E402

GET_STATUS = "urn:gymact:kubernetes-reconciliation:capability:get_status"
SCALE_RESTART = "urn:gymact:kubernetes-reconciliation:capability:scale_restart"
# kubernetes_reconciliation.py's requires_authority now defaults to True (a
# real DO capability against a real cluster must not run unauthorized) --
# every test below explicitly admits AUTHORITY.
AUTHORITY = "urn:test:kubernetes-reconciliation-authority"


def _authorized_gym() -> GymAct:
    gym = GymAct(authority_resolver=AllowListAuthorityResolver({AUTHORITY}))
    gym.register_provider(KubernetesReconciliationProvider())
    return gym


async def _run_real_kubernetes_episode() -> list:
    """One real episode: materialize -> verify (no receipt; an independent
    read, per `gymact.kernel.GymAct.verify`) -> act (scale_restart, a real DO
    capability) -> teardown. GET_STATUS is Consequence.READ, which `act()`
    correctly refuses (READ_CAPABILITY_IS_NOT_ACTUATION) -- reads happen via
    `observe()`/`verify()`, not `act()`."""
    gym = _authorized_gym()
    receipts = []

    materialization = await gym.materialize(
        MaterializationIntent(provider="kubernetes-reconciliation", config={})
    )
    assert materialization.accepted is True
    receipts.append(materialization.receipt)
    episode_id = materialization.episode.episode_id

    verification = await gym.verify(episode_id, {"running": True})
    assert verification.passed is True

    result = await gym.act(
        ActuationIntent(episode_id=episode_id, capability=SCALE_RESTART, authority_ref=AUTHORITY)
    )
    assert result.accepted is True
    receipts.append(result.receipt)

    verification_after = await gym.verify(episode_id, {"running": True})
    assert verification_after.passed is True

    receipts.append(await gym.teardown(episode_id, authority_ref=AUTHORITY))
    return receipts


async def test_real_pod_materializes_and_converges_to_running_on_the_real_cluster() -> None:
    gym = GymAct()
    gym.register_provider(KubernetesReconciliationProvider())

    materialization = await gym.materialize(
        MaterializationIntent(provider="kubernetes-reconciliation", config={})
    )
    assert materialization.accepted is True
    episode_id = materialization.episode.episode_id

    # Real cluster-observed state right after apply: the pod may not be
    # Running yet (image pull, scheduling) -- this is real state, not a
    # canned value.
    observed = await gym.observe(episode_id)
    assert observed.state["pod_name"]
    assert observed.state["namespace"] == "default"

    # verify() polls REAL cluster-observed state (kubectl get pod -o json's
    # .status.phase) until Running or a bounded timeout -- this is the exact
    # gap named in the audit: not just kubectl apply's exit code.
    verification = await gym.verify(episode_id, {"running": True})
    assert verification.passed is True
    assert verification.observed["phase"] == "Running"

    await gym.teardown(episode_id)


async def test_scale_restart_capability_is_real_and_forces_real_rescheduling() -> None:
    gym = _authorized_gym()
    m = await gym.materialize(
        MaterializationIntent(provider="kubernetes-reconciliation", config={})
    )
    episode_id = m.episode.episode_id

    v = await gym.verify(episode_id, {"running": True})
    assert v.passed is True

    result = await gym.act(
        ActuationIntent(episode_id=episode_id, capability=SCALE_RESTART, authority_ref=AUTHORITY)
    )
    assert result.accepted is True
    assert result.effect["apply_returncode"] == 0

    # The real pod must converge back to Running after the real
    # delete+reapply -- polled against real cluster state again.
    verification = await gym.verify(episode_id, {"running": True})
    assert verification.passed is True

    await gym.teardown(episode_id, authority_ref=AUTHORITY)


async def test_teardown_really_deletes_the_pod_from_the_real_cluster() -> None:
    gym = _authorized_gym()
    m = await gym.materialize(
        MaterializationIntent(provider="kubernetes-reconciliation", config={})
    )
    episode_id = m.episode.episode_id
    env = gym._episodes[
        episode_id
    ].environment  # real environment handle, captured before teardown removes the episode

    receipt = await gym.teardown(episode_id, authority_ref=AUTHORITY)
    assert receipt.standing == Standing.ALIVE

    # Real confirmation against the real cluster -- not trusting
    # teardown()'s own bookkeeping.
    assert env.is_really_deleted() is True


async def test_kubernetes_episode_replays_conformant_and_produces_a_valid_ocel_log() -> None:
    receipts = await _run_real_kubernetes_episode()
    operations = [r.operation for r in receipts]

    assert operations == [
        Operation.MATERIALIZE,
        Operation.ACT,
        Operation.TEARDOWN,
    ]

    result = ConformanceChecker().check(operations)
    assert result.conformant is True

    log = receipts_to_ocel(receipts)
    validate_ocel_log(log)  # real jsonschema.validate against real OCEL 2.0 schema
