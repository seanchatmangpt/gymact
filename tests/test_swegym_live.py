"""Chicago-style: a real GymAct episode driven against a real Docker daemon
and a real upstream SWE-Gym HuggingFace dataset row -- not simulated.

This promotes what was already hand-verified live in this session (real
`docker pull`/`docker run` of `xingyaoww/sweb.eval.x86_64.getmoto_s_moto-5752`,
a real HuggingFace dataset row, a real 3-tier patch apply, real pytest
FAIL_TO_PASS/PASS_TO_PASS execution) into permanent, repeatable test
coverage, closing the real gap named in the swegym capability-coverage
audit: `swegym.evaluate-patch` had no test exercising its real success path
-- only the four refusal paths (unsupported binding, missing/malformed
payload) were covered.

Per `gymact.standing.require_standing`, the real thing is the default: if
Docker is not reachable, this module FAILS unless the run explicitly sets
`GYMACT_ALLOW_DEGRADED_STANDINGS` to include "LOCAL_GYM:swegym" (or "*") --
a skip here is something a run must opt into, never something it silently
gets. Matches `test_kubernetes_reconciliation.py`'s contract exactly.

The task_id used (`getmoto__moto-5752`, from `SWE-Gym/SWE-Gym`) is the exact
subject this session's manual live verification already proved solvable via
its own upstream gold patch, and unsolvable via an empty candidate patch --
chosen for a fast, small (~1.15GB) image, not cherry-picked for a specific
pass/fail outcome unrelated to what the patch actually does.
"""

from __future__ import annotations

import shutil
import subprocess

from gymact.standing import require_standing


def _docker_available() -> bool:
    if shutil.which("docker") is None:
        return False
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


def _datasets_available() -> bool:
    try:
        import datasets  # noqa: F401
    except ImportError:
        return False
    return True


require_standing(
    "LOCAL_GYM:swegym",
    available=_docker_available() and _datasets_available(),
    reason=(
        "no reachable Docker daemon, or the optional 'datasets' package is not "
        "installed (pip/uv install the 'gyms' extra: `uv sync --extra gyms`)"
    ),
)

from gymact import AllowListAuthorityResolver, GymAct, MaterializationIntent  # noqa: E402
from gymact.gyms.swegym import SWEGYM_EVALUATE_CAPABILITY, SWEGymProvider  # noqa: E402
from gymact.models import ActuationIntent  # noqa: E402
from gymact.ocel import validate_ocel_log  # noqa: E402
from gymact.process import ConformanceChecker  # noqa: E402

AUTHORITY = "urn:test:swegym-live-authority"
TASK_ID = "getmoto__moto-5752"


def _authorized_gym() -> GymAct:
    gym = GymAct(authority_resolver=AllowListAuthorityResolver({AUTHORITY}))
    gym.register_provider(SWEGymProvider())
    return gym


def _gold_patch() -> str:
    """Real gold patch for TASK_ID, fetched live from the real upstream dataset."""
    from datasets import load_dataset

    dataset = load_dataset("SWE-Gym/SWE-Gym", split="train")
    row = next(candidate for candidate in dataset if candidate["instance_id"] == TASK_ID)
    return row["patch"]


async def test_real_gold_patch_resolves_the_real_task_via_real_docker_grading() -> None:
    """A real container is pulled/started, the real held-out test suites run
    for real inside it, and the task's own real gold patch makes them pass --
    this is `resolved=True` derived from real, independently observed test
    outcomes, never from an actuator's own success report."""
    gym = _authorized_gym()

    materialization = await gym.materialize(
        MaterializationIntent(
            provider="swegym", config={"task_id": TASK_ID}, authority_ref=AUTHORITY
        )
    )
    assert materialization.accepted is True, materialization.receipt.reason
    episode_id = materialization.episode.episode_id

    outcome = await gym.act(
        ActuationIntent(
            episode_id=episode_id,
            capability=SWEGYM_EVALUATE_CAPABILITY.iri,
            payload={"patch": _gold_patch()},
            authority_ref=AUTHORITY,
        )
    )
    assert outcome.accepted is True
    after = outcome.effect["after"] if isinstance(outcome.effect, dict) else {}
    assert after.get("resolved") is True, after
    assert after.get("fail_to_pass_results", {}).get("passed") is True
    assert after.get("pass_to_pass_results", {}).get("passed") is True
    assert after.get("new_pass_to_pass_regressions") == []

    verification = await gym.verify(episode_id, {"resolved": True})
    assert verification.passed is True

    await gym.teardown(episode_id)

    ocel_log = gym.episode_ocel_log(episode_id)
    validate_ocel_log(ocel_log)
    events = sorted(ocel_log["events"], key=lambda e: e["time"])
    from gymact.models import Operation

    conformance = ConformanceChecker().check([Operation(e["type"]) for e in events])
    assert conformance.conformant, conformance.deviations


async def test_real_empty_patch_does_not_resolve_the_real_task() -> None:
    """The negative case, run against the SAME real task and image: an
    empty candidate patch (only the held-out test_patch applied) must never
    resolve -- proves `resolved` is a real, independently computed judgment,
    not a constant the provider always returns True for."""
    gym = _authorized_gym()

    materialization = await gym.materialize(
        MaterializationIntent(
            provider="swegym", config={"task_id": TASK_ID}, authority_ref=AUTHORITY
        )
    )
    assert materialization.accepted is True
    episode_id = materialization.episode.episode_id

    outcome = await gym.act(
        ActuationIntent(
            episode_id=episode_id,
            capability=SWEGYM_EVALUATE_CAPABILITY.iri,
            payload={"patch": ""},
            authority_ref=AUTHORITY,
        )
    )
    assert outcome.accepted is True
    after = outcome.effect["after"] if isinstance(outcome.effect, dict) else {}
    assert after.get("resolved") is False, after
    assert after.get("fail_to_pass_results", {}).get("passed") is False
    assert after.get("new_pass_to_pass_regressions") == []

    verification = await gym.verify(episode_id, {"resolved": False})
    assert verification.passed is True

    await gym.teardown(episode_id)
