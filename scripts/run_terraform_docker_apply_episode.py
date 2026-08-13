#!/usr/bin/env python3
"""Run one real GymAct episode over `TerraformDockerApplyProvider` -- a real
`terraform apply`/`destroy` of the checked-in `gyms/fixtures/terraform_docker`
config against colima's real local Docker daemon -- and write a real OCEL
2.0 log at reports/ocel/terraform-docker-apply/episode.ocel.json.

Mirrors `scripts/run_dev_portfolio_episode.py`'s real shape (materialize ->
act -> verify -> teardown -> write_ocel_log), with an authority-gated `DO`
path: `TerraformDockerApplyProvider.materialization_requires_authority` is
False but the `apply`/`destroy` capabilities themselves default
`requires_authority=True` on the environment (a real `docker_image` +
`docker_container` mutation must not run unauthorized) -- see the module's
own docstring for why `apply`/`destroy` are safe here specifically (fixed,
small, auditable, local-only blast radius) unlike `terraform_plan.py`.

Per `gymact.standing.require_standing`, this script refuses to run (loud,
not silent) if no real `terraform`/`tofu` binary is on PATH or the real
local Docker daemon is unreachable -- matching
`tests/test_terraform_docker_apply.py`'s own gate.

Usage:
    uv run python scripts/run_terraform_docker_apply_episode.py
"""

from __future__ import annotations

import asyncio
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from gymact import AllowListAuthorityResolver, GymAct, MaterializationIntent
from gymact.gyms.terraform_docker_apply import TerraformDockerApplyProvider
from gymact.models import ActuationIntent
from gymact.ocel import write_ocel_log
from gymact.standing import require_standing

REPORTS_DIR = Path(__file__).parent.parent / "reports" / "ocel"

APPLY = "urn:gymact:terraform-docker-apply:capability:apply"
DESTROY = "urn:gymact:terraform-docker-apply:capability:destroy"
AUTHORITY = "urn:gymact:terraform-docker-apply-episode:authority"


def _binary_available() -> bool:
    return shutil.which("terraform") is not None or shutil.which("tofu") is not None


def _real_docker_reachable() -> bool:
    try:
        result = subprocess.run(
            ["docker", "info"], capture_output=True, text=True, timeout=10.0, check=False
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


async def run() -> None:
    gym = GymAct(authority_resolver=AllowListAuthorityResolver({AUTHORITY}))
    gym.register_provider(TerraformDockerApplyProvider())
    receipts = []
    log_path = REPORTS_DIR / "terraform-docker-apply" / "episode.ocel.json"

    materialization = await gym.materialize(
        MaterializationIntent(provider="terraform-docker-apply", config={})
    )
    receipts.append(materialization.receipt)
    if not materialization.accepted or materialization.episode is None:
        print(f"terraform-docker-apply: materialization refused: {materialization.receipt.reason}")
        log, digest = write_ocel_log(log_path, receipts)
        print(f"terraform-docker-apply: {len(log['events'])} events, sha256={digest}")
        return

    episode_id = materialization.episode.episode_id

    try:
        apply_result = await gym.act(
            ActuationIntent(episode_id=episode_id, capability=APPLY, authority_ref=AUTHORITY)
        )
        print(
            f"terraform-docker-apply: apply accepted={apply_result.accepted} "
            f"returncode={apply_result.effect.get('after', {}).get('apply_returncode') if apply_result.effect else None}"
        )

        verification = await gym.verify(episode_id, {"container_running": True})
        print(f"terraform-docker-apply: verify_running_passed={verification.passed}")

        # Real solved=True evidence recorded directly on the apply act
        # event's own reason attribute -- matching
        # scripts/run_togaf_episode.py's precedent, so
        # tests/test_ocel_standing.py's real replay-based derivation can
        # find it on this act event, not on a separate summary.
        receipts.append(
            apply_result.receipt.model_copy(
                update={"reason": f"solved={verification.passed}"}
            )
        )
    finally:
        # Real cleanup, always attempted: destroy + confirm via docker
        # inspect, never leak the real container even on assertion/error.
        destroy_result = await gym.act(
            ActuationIntent(episode_id=episode_id, capability=DESTROY, authority_ref=AUTHORITY)
        )
        receipts.append(destroy_result.receipt)
        print(f"terraform-docker-apply: destroy accepted={destroy_result.accepted}")

        gone_verification = await gym.verify(episode_id, {"container_running": False})
        print(f"terraform-docker-apply: verify_gone_passed={gone_verification.passed}")

        receipts.append(await gym.teardown(episode_id, authority_ref=AUTHORITY))

    log, digest = write_ocel_log(log_path, receipts)
    print(f"terraform-docker-apply: {len(log['events'])} events, sha256={digest}")


if __name__ == "__main__":
    asyncio.run(run())
