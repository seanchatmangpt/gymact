"""Chicago-style: a real GymAct episode driving real `terraform apply`/
`destroy` against colima's real local Docker daemon via the checked-in
`gyms/fixtures/terraform_docker` config -- not simulated.

Per `gymact.standing.require_standing`, the real thing is the default: if no
real `terraform`/`tofu` binary is on PATH, or the real local Docker daemon
is not reachable, this module FAILS unless the run explicitly sets
`GYMACT_ALLOW_DEGRADED_STANDINGS` to include
"LOCAL_GYM:terraform-docker-apply" (or "*") -- a skip here is something a
run must opt into, never something it silently gets. Matches
`test_kubernetes_reconciliation.py`'s contract.

Every mid-test failure path still attempts real cleanup (terraform destroy,
confirmed via real `docker inspect`) via try/finally, so a failing assertion
never leaks a real container.
"""

from __future__ import annotations

import shutil
import subprocess

from gymact.standing import require_standing


def _binary_available() -> bool:
    return shutil.which("terraform") is not None or shutil.which("tofu") is not None


def _real_docker_reachable() -> bool:
    try:
        result = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            text=True,
            timeout=10.0,
            check=False,
        )
        return result.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


require_standing(
    "LOCAL_GYM:terraform-docker-apply",
    available=_binary_available() and _real_docker_reachable(),
    reason="no 'terraform'/'tofu' on PATH or no reachable local Docker daemon "
    "(start colima: `colima start`)",
)

from gymact import AllowListAuthorityResolver, GymAct, MaterializationIntent  # noqa: E402
from gymact.gyms.terraform_docker_apply import (  # noqa: E402
    TerraformDockerApplyProvider,
)
from gymact.models import ActuationIntent, Operation, Standing  # noqa: E402
from gymact.ocel import receipts_to_ocel, validate_ocel_log, write_ocel_log  # noqa: E402
from gymact.process import ConformanceChecker  # noqa: E402

APPLY = "urn:gymact:terraform-docker-apply:capability:apply"
DESTROY = "urn:gymact:terraform-docker-apply:capability:destroy"
PLAN = "urn:gymact:terraform-docker-apply:capability:plan"
# terraform_docker_apply.py's requires_authority now defaults to True (real
# apply/destroy against a real Docker daemon must not run unauthorized) --
# every act()-driving test below explicitly admits AUTHORITY.
AUTHORITY = "urn:test:terraform-docker-apply-authority"


def _authorized_gym() -> GymAct:
    gym = GymAct(authority_resolver=AllowListAuthorityResolver({AUTHORITY}))
    gym.register_provider(TerraformDockerApplyProvider())
    return gym


async def test_real_terraform_plan_runs_read_only_against_the_checked_in_config() -> None:
    gym = GymAct()
    gym.register_provider(TerraformDockerApplyProvider())
    m = await gym.materialize(MaterializationIntent(provider="terraform-docker-apply", config={}))
    assert m.accepted is True
    episode_id = m.episode.episode_id
    env = gym._episodes[episode_id].environment
    try:
        plan_capability = next(c for c in env.capabilities() if c.binding == "plan")
        effect = await env.actuate(plan_capability, {})
        assert effect["after"]["plan_attempted"] is True
        assert effect["after"]["plan_returncode"] == 0
        assert "docker_container.app will be created" in effect["after"]["plan_stdout"]
    finally:
        await gym.teardown(episode_id)


async def test_real_apply_creates_a_real_running_container_verified_via_docker() -> None:
    gym = _authorized_gym()
    m = await gym.materialize(MaterializationIntent(provider="terraform-docker-apply", config={}))
    assert m.accepted is True
    episode_id = m.episode.episode_id
    env = gym._episodes[episode_id].environment
    try:
        result = await gym.act(
            ActuationIntent(episode_id=episode_id, capability=APPLY, authority_ref=AUTHORITY)
        )
        assert result.accepted is True
        assert result.effect["after"]["apply_returncode"] == 0

        # verify() polls REAL `docker inspect`-observed container state --
        # never trusts terraform apply's exit code alone.
        verification = await gym.verify(episode_id, {"container_running": True})
        assert verification.passed is True
        assert verification.observed["container_running"] is True
        assert verification.observed["container"] is not None
        assert verification.observed["container"]["Name"].lstrip("/") == env._container_name
    finally:
        # Real cleanup even on assertion failure: destroy + confirm via
        # docker inspect, never leak the container.
        destroy_result = await gym.act(
            ActuationIntent(episode_id=episode_id, capability=DESTROY, authority_ref=AUTHORITY)
        )
        assert destroy_result.accepted is True
        gone_verification = await gym.verify(episode_id, {"container_running": False})
        assert gone_verification.passed is True
        assert gone_verification.observed["container"] is None
        await gym.teardown(episode_id, authority_ref=AUTHORITY)


async def test_teardown_really_destroys_and_confirms_via_real_docker_inspect() -> None:
    gym = _authorized_gym()
    m = await gym.materialize(MaterializationIntent(provider="terraform-docker-apply", config={}))
    episode_id = m.episode.episode_id
    env = gym._episodes[episode_id].environment
    try:
        result = await gym.act(
            ActuationIntent(episode_id=episode_id, capability=APPLY, authority_ref=AUTHORITY)
        )
        assert result.accepted is True
        verification = await gym.verify(episode_id, {"container_running": True})
        assert verification.passed is True

        receipt = await gym.teardown(episode_id, authority_ref=AUTHORITY)
        assert receipt.standing == Standing.ALIVE

        # Real confirmation against the real Docker daemon -- not trusting
        # teardown()'s own bookkeeping.
        assert env.is_really_gone() is True
    except Exception:
        # If the primary assertions above already tore down, this is a
        # harmless no-op (env.teardown() is idempotent); otherwise this is
        # exactly the real-cleanup safety net the task requires.
        if not env._closed:
            await env.teardown()
        raise


async def _run_real_episode() -> list:
    """One real episode: materialize -> act (apply, a real DO capability)
    -> verify -> act (destroy) -> verify -> teardown."""
    gym = _authorized_gym()
    receipts = []

    materialization = await gym.materialize(
        MaterializationIntent(provider="terraform-docker-apply", config={})
    )
    assert materialization.accepted is True
    receipts.append(materialization.receipt)
    episode_id = materialization.episode.episode_id
    env = gym._episodes[episode_id].environment

    try:
        apply_result = await gym.act(
            ActuationIntent(episode_id=episode_id, capability=APPLY, authority_ref=AUTHORITY)
        )
        assert apply_result.accepted is True
        receipts.append(apply_result.receipt)

        verification = await gym.verify(episode_id, {"container_running": True})
        assert verification.passed is True

        destroy_result = await gym.act(
            ActuationIntent(episode_id=episode_id, capability=DESTROY, authority_ref=AUTHORITY)
        )
        assert destroy_result.accepted is True
        receipts.append(destroy_result.receipt)

        gone_verification = await gym.verify(episode_id, {"container_running": False})
        assert gone_verification.passed is True
    finally:
        if not env._closed:
            receipts.append(await gym.teardown(episode_id, authority_ref=AUTHORITY))

    return receipts


async def test_terraform_docker_episode_replays_conformant_and_produces_a_valid_ocel_log(
    tmp_path,
) -> None:
    receipts = await _run_real_episode()
    operations = [r.operation for r in receipts]

    assert operations == [
        Operation.MATERIALIZE,
        Operation.ACT,
        Operation.ACT,
        Operation.TEARDOWN,
    ]

    result = ConformanceChecker().check(operations)
    assert result.conformant is True

    log = receipts_to_ocel(receipts)
    validate_ocel_log(log)  # real jsonschema.validate against real OCEL 2.0 schema

    # Real persistence + digest, per gymact.ocel.write_ocel_log's contract:
    # validated before being written, digest taken over the exact bytes on
    # disk.
    log_path = tmp_path / "terraform-docker-apply-episode.ocel.json"
    written_log, digest = write_ocel_log(log_path, receipts)
    assert written_log == log
    assert log_path.is_file()
    assert len(digest) == 64  # real sha256 hex digest
