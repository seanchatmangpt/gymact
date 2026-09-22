"""Chicago-style: a real GymAct episode driven against a real local
Kubernetes cluster (`kind`/`k3d`/colima `--kubernetes`), applying the REAL,
checked-out kubernetes-goat scenario manifests (pinned in
`~/autofde-lab/docs/papers/gym-lock.ttl` as `vendor-kubernetes-goat` at
`723a0db478f050d173d23b4ce5044b65bce0bdd0`) via real `kubectl` subprocess
calls -- not simulated, and not the generic reconstructed manifest
`kubernetes_reconciliation.py` uses.

Per `gymact.standing.require_standing`, real is the default: this module
FAILS unless BOTH a real Kubernetes cluster is reachable on the current
kubeconfig context AND the real vendored kubernetes-goat checkout exists on
disk at the pinned revision -- unless the run explicitly sets
`GYMACT_ALLOW_DEGRADED_STANDINGS` to include
"LOCAL_GYM:kubernetes-goat" (or "*"). Matches
`test_kubernetes_reconciliation.py`'s contract.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from gymact.standing import require_standing

_VENDORED_CHECKOUT = Path.home() / "autofde-lab" / "vendor" / "gyms" / "kubernetes-goat"
_PINNED_REVISION = "723a0db478f050d173d23b4ce5044b65bce0bdd0"


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


def _vendored_checkout_at_pinned_revision() -> bool:
    """Confirms the real vendored kubernetes-goat checkout is present AND
    checked out to the exact SHA pinned in gym-lock.ttl -- an importable
    directory that drifted from the pin is not the admitted vendor state."""
    head_ref_file = _VENDORED_CHECKOUT / ".git" / "HEAD"
    if not head_ref_file.is_file():
        return False
    head_contents = head_ref_file.read_text().strip()
    if head_contents.startswith("ref: "):
        ref_path = _VENDORED_CHECKOUT / ".git" / head_contents[len("ref: ") :]
        if not ref_path.is_file():
            return False
        sha = ref_path.read_text().strip()
    else:
        sha = head_contents
    return sha == _PINNED_REVISION


require_standing(
    "LOCAL_GYM:kubernetes-goat",
    available=_real_cluster_reachable() and _vendored_checkout_at_pinned_revision(),
    reason="no reachable Kubernetes cluster on the current kubeconfig context, or the "
    "real vendored kubernetes-goat checkout at "
    f"{_VENDORED_CHECKOUT} is missing/not at the pinned revision {_PINNED_REVISION} "
    "(start a cluster locally: `kind create cluster`; and ensure autofde-lab's "
    "vendor checkout is present at the pinned gym-lock.ttl revision)",
)

from gymact import GymAct, MaterializationIntent  # noqa: E402
from gymact.authority import AllowListAuthorityResolver  # noqa: E402
from gymact.gyms.kubernetes_goat import KubernetesGoatProvider  # noqa: E402
from gymact.models import ActuationIntent, Operation, Standing  # noqa: E402
from gymact.ocel import receipts_to_ocel, validate_ocel_log  # noqa: E402
from gymact.process import ConformanceChecker  # noqa: E402

GET_JOB_STATUS = "urn:gymact:kubernetes-goat:capability:get_job_status"
GET_LOGS = "urn:gymact:kubernetes-goat:capability:get_logs"
RERUN_SCENARIO = "urn:gymact:kubernetes-goat:capability:rerun_scenario"

_AUTHORITY_REF = "urn:gymact:test-authority:kubernetes-goat"
_CONFIG = {"checkout_path": str(_VENDORED_CHECKOUT)}


def _resolver() -> AllowListAuthorityResolver:
    return AllowListAuthorityResolver(allowed=[_AUTHORITY_REF])


async def test_materialize_is_refused_without_authority() -> None:
    """Deploying a real kubernetes-goat scenario is a real consequential
    operation -- the default DenyAuthorityResolver must refuse it, matching
    .claude/rules/actuation-authority.md's fail-closed invariant."""
    gym = GymAct()
    gym.register_provider(KubernetesGoatProvider())

    materialization = await gym.materialize(
        MaterializationIntent(
            provider="kubernetes-goat", scenario="batch-check", config=_CONFIG
        )
    )
    assert materialization.accepted is False
    assert materialization.standing == Standing.REFUSED


async def test_unknown_checkout_path_is_rejected_not_fabricated() -> None:
    gym = GymAct(authority_resolver=_resolver())
    gym.register_provider(KubernetesGoatProvider())
    materialization = await gym.materialize(
        MaterializationIntent(
            provider="kubernetes-goat",
            scenario="batch-check",
            config={"checkout_path": "/nonexistent/path/does/not/exist"},
            authority_ref=_AUTHORITY_REF,
        )
    )
    assert materialization.accepted is False


async def test_real_batch_check_scenario_materializes_from_the_real_manifest_and_completes() -> (
    None
):
    gym = GymAct(authority_resolver=_resolver())
    gym.register_provider(KubernetesGoatProvider())

    materialization = await gym.materialize(
        MaterializationIntent(
            provider="kubernetes-goat",
            scenario="batch-check",
            config=_CONFIG,
            authority_ref=_AUTHORITY_REF,
        )
    )
    assert materialization.accepted is True
    episode_id = materialization.episode.episode_id

    observed = await gym.observe(episode_id)
    assert observed.state["scenario"] == "batch-check"
    assert observed.state["job_name"] == "batch-check-job"
    assert observed.state["namespace"].startswith("gymact-k8s-goat-")

    # verify() polls REAL cluster-observed Job status
    # (kubectl get job -o json's .status.succeeded) until the real,
    # vendored kubernetes-goat container really completes, or a bounded
    # timeout -- never trusts kubectl apply's exit code as completion.
    verification = await gym.verify(episode_id, {"succeeded": True})
    assert verification.passed is True
    assert verification.observed["failed"] is False

    await gym.teardown(episode_id, authority_ref=_AUTHORITY_REF)


async def test_teardown_requires_authority_and_really_deletes_the_namespace() -> None:
    gym = GymAct(authority_resolver=_resolver())
    gym.register_provider(KubernetesGoatProvider())
    m = await gym.materialize(
        MaterializationIntent(
            provider="kubernetes-goat",
            scenario="batch-check",
            config=_CONFIG,
            authority_ref=_AUTHORITY_REF,
        )
    )
    episode_id = m.episode.episode_id

    # Teardown without authority must be refused, not silently permitted.
    refused = await gym.teardown(episode_id)
    assert refused.standing == Standing.REFUSED

    env = gym._episodes[
        episode_id
    ].environment  # real environment handle, captured before teardown removes the episode

    receipt = await gym.teardown(episode_id, authority_ref=_AUTHORITY_REF)
    assert receipt.standing == Standing.ALIVE

    # Real confirmation against the real cluster -- not trusting
    # teardown()'s own bookkeeping.
    assert env.is_really_deleted() is True


async def test_rerun_scenario_capability_is_real_do_and_forces_real_rerun() -> None:
    gym = GymAct(authority_resolver=_resolver())
    gym.register_provider(KubernetesGoatProvider())
    m = await gym.materialize(
        MaterializationIntent(
            provider="kubernetes-goat",
            scenario="batch-check",
            config=_CONFIG,
            authority_ref=_AUTHORITY_REF,
        )
    )
    episode_id = m.episode.episode_id

    v = await gym.verify(episode_id, {"succeeded": True})
    assert v.passed is True

    # Real DO capability requires real authority admission too.
    refused = await gym.act(ActuationIntent(episode_id=episode_id, capability=RERUN_SCENARIO))
    assert refused.accepted is False
    assert refused.standing == Standing.REFUSED

    result = await gym.act(
        ActuationIntent(
            episode_id=episode_id, capability=RERUN_SCENARIO, authority_ref=_AUTHORITY_REF
        )
    )
    assert result.accepted is True
    assert result.effect["apply_returncode"] == 0

    # The real Job must reconverge to succeeded after the real
    # delete+reapply -- polled against real cluster state again.
    verification = await gym.verify(episode_id, {"succeeded": True})
    assert verification.passed is True

    await gym.teardown(episode_id, authority_ref=_AUTHORITY_REF)


async def test_read_capabilities_are_not_actuation() -> None:
    gym = GymAct(authority_resolver=_resolver())
    gym.register_provider(KubernetesGoatProvider())
    m = await gym.materialize(
        MaterializationIntent(
            provider="kubernetes-goat",
            scenario="batch-check",
            config=_CONFIG,
            authority_ref=_AUTHORITY_REF,
        )
    )
    episode_id = m.episode.episode_id

    status_result = await gym.act(
        ActuationIntent(
            episode_id=episode_id, capability=GET_JOB_STATUS, authority_ref=_AUTHORITY_REF
        )
    )
    assert status_result.accepted is False
    assert status_result.standing == Standing.REFUSED
    assert status_result.receipt.reason == "READ_CAPABILITY_IS_NOT_ACTUATION"

    logs_result = await gym.act(
        ActuationIntent(episode_id=episode_id, capability=GET_LOGS, authority_ref=_AUTHORITY_REF)
    )
    assert logs_result.accepted is False

    await gym.teardown(episode_id, authority_ref=_AUTHORITY_REF)


async def test_hidden_in_layers_scenario_materializes_from_its_own_real_manifest() -> None:
    """A second real, distinct vendored scenario -- confirms this provider
    is not hardcoded to a single manifest."""
    gym = GymAct(authority_resolver=_resolver())
    gym.register_provider(KubernetesGoatProvider())
    m = await gym.materialize(
        MaterializationIntent(
            provider="kubernetes-goat",
            scenario="hidden-in-layers",
            config=_CONFIG,
            authority_ref=_AUTHORITY_REF,
        )
    )
    assert m.accepted is True
    episode_id = m.episode.episode_id
    observed = await gym.observe(episode_id)
    assert observed.state["job_name"] == "hidden-in-layers"

    verification = await gym.verify(episode_id, {"succeeded": True})
    assert verification.passed is True

    await gym.teardown(episode_id, authority_ref=_AUTHORITY_REF)


async def test_kubernetes_goat_episode_replays_conformant_and_produces_a_valid_ocel_log() -> None:
    gym = GymAct(authority_resolver=_resolver())
    gym.register_provider(KubernetesGoatProvider())
    receipts = []

    m = await gym.materialize(
        MaterializationIntent(
            provider="kubernetes-goat",
            scenario="batch-check",
            config=_CONFIG,
            authority_ref=_AUTHORITY_REF,
        )
    )
    assert m.accepted is True
    receipts.append(m.receipt)
    episode_id = m.episode.episode_id

    verification = await gym.verify(episode_id, {"succeeded": True})
    assert verification.passed is True

    act_result = await gym.act(
        ActuationIntent(
            episode_id=episode_id, capability=RERUN_SCENARIO, authority_ref=_AUTHORITY_REF
        )
    )
    assert act_result.accepted is True
    receipts.append(act_result.receipt)

    verification_after = await gym.verify(episode_id, {"succeeded": True})
    assert verification_after.passed is True

    receipts.append(await gym.teardown(episode_id, authority_ref=_AUTHORITY_REF))

    operations = [r.operation for r in receipts]
    assert operations == [Operation.MATERIALIZE, Operation.ACT, Operation.TEARDOWN]

    result = ConformanceChecker().check(operations)
    assert result.conformant is True

    log = receipts_to_ocel(receipts)
    validate_ocel_log(log)  # real jsonschema.validate against real OCEL 2.0 schema
