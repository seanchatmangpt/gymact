#!/usr/bin/env python3
"""Run one real GymAct episode over `TerraformPlanProvider` -- a real
`terraform`/`tofu` `init`/`plan` against the real, already-checked-out
terragoat/alicloud configuration directory -- and write a real OCEL 2.0 log
at reports/ocel/terraform-plan/episode.ocel.json.

Mirrors `scripts/run_terraform_docker_apply_episode.py`'s real shape
(materialize -> act -> verify -> teardown -> write_ocel_log). Unlike that
script, there is no `apply`/`destroy` here at all -- `terraform_plan.py`'s
`actuate()` has no dispatch branch for either (see that module's docstring);
this episode only ever runs `init`, `plan`, and (at materialize time)
`graph`.

Per `gymact.standing.require_standing`, this script refuses to run (loud,
not silent) if no real `terraform`/`tofu` binary is on PATH or the real
terragoat checkout at `~/autofde-lab/vendor/gyms/terragoat` has no real `.tf`
files -- matching `tests/test_terraform_plan.py`'s own gate.

Usage:
    uv run python scripts/run_terraform_plan_episode.py
"""

from __future__ import annotations

import asyncio
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from gymact import AllowListAuthorityResolver, GymAct, MaterializationIntent
from gymact.gyms.terraform_plan import TerraformPlanProvider
from gymact.models import ActuationIntent
from gymact.ocel import write_ocel_log
from gymact.standing import require_standing

REPORTS_DIR = Path(__file__).parent.parent / "reports" / "ocel"
_TERRAGOAT_TARGET_DIR = (
    Path.home() / "autofde-lab" / "vendor" / "gyms" / "terragoat" / "terraform" / "alicloud"
)

PLAN = "urn:gymact:terraform-plan:capability:plan"
AUTHORITY = "urn:gymact:terraform-plan-episode:authority"


def _binary_available() -> bool:
    return shutil.which("terraform") is not None or shutil.which("tofu") is not None


def _checkout_present() -> bool:
    return _TERRAGOAT_TARGET_DIR.is_dir() and any(_TERRAGOAT_TARGET_DIR.glob("*.tf"))


require_standing(
    "LOCAL_GYM:terraform-plan",
    available=_binary_available() and _checkout_present(),
    reason="no 'terraform'/'tofu' on PATH, or no real terragoat/alicloud .tf checkout at "
    f"{_TERRAGOAT_TARGET_DIR} (clone ~/autofde-lab's terragoat submodule; install terraform "
    "or tofu)",
)


async def run() -> None:
    gym = GymAct(authority_resolver=AllowListAuthorityResolver({AUTHORITY}))
    gym.register_provider(TerraformPlanProvider())
    receipts = []
    log_path = REPORTS_DIR / "terraform-plan" / "episode.ocel.json"

    materialization = await gym.materialize(
        MaterializationIntent(
            provider="terraform-plan", config={"working_dir": str(_TERRAGOAT_TARGET_DIR)}
        )
    )
    receipts.append(materialization.receipt)
    if not materialization.accepted or materialization.episode is None:
        print(f"terraform-plan: materialization refused: {materialization.receipt.reason}")
        log, digest = write_ocel_log(log_path, receipts)
        print(f"terraform-plan: {len(log['events'])} events, sha256={digest}")
        return

    episode_id = materialization.episode.episode_id

    plan_result = await gym.act(
        ActuationIntent(episode_id=episode_id, capability=PLAN, authority_ref=AUTHORITY)
    )
    print(
        f"terraform-plan: plan accepted={plan_result.accepted} "
        f"returncode={plan_result.effect.get('after', {}).get('plan_returncode') if plan_result.effect else None}"
    )

    # Empty expected dict routes verify() through
    # gymact.verify_replay.terraform_plan_verify_from_log -- the same
    # real-plan-completed check the log-replay path reuses (see
    # terraform_plan.py's verify() docstring).
    verification = await gym.verify(episode_id, {})
    print(f"terraform-plan: verify_passed={verification.passed}")

    # Real solved=True evidence recorded directly on the plan act event's
    # own reason attribute -- matching scripts/run_togaf_episode.py's and
    # scripts/run_terraform_docker_apply_episode.py's precedent, so
    # tests/test_ocel_standing.py's real replay-based derivation can find it
    # on this act event, not on a separate summary.
    receipts.append(
        plan_result.receipt.model_copy(update={"reason": f"solved={verification.passed}"})
    )

    receipts.append(await gym.teardown(episode_id, authority_ref=AUTHORITY))

    log, digest = write_ocel_log(log_path, receipts)
    print(f"terraform-plan: {len(log['events'])} events, sha256={digest}")


if __name__ == "__main__":
    asyncio.run(run())
