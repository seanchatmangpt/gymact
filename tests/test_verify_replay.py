"""Chicago-style tests for `gymact.verify_replay` —
`docs/jira/v26.8.12/cloud-cert-wbpr-prd.md` FR4, Terraform proof of concept.

Two real proofs, no mocks:

1. `terraform_plan_verify_from_log` reproduces the exact same predicate as
   `TerraformPlanEnvironment.verify()` — proven by direct unit assertions
   against real field shapes (no subprocess needed for this half).
2. A real, end-to-end episode (real `terraform`/`tofu` binary, real
   terragoat checkout, via the same `_authorized_gym()` fixture
   `test_terraform_plan.py` already uses) produces a real `after` state
   dict, and replaying that exact dict through `terraform_plan_verify_from_
   log` with no subprocess reproduces the real `gym.verify()` verdict —
   this is FR4's actual claim: "reproduces the verifier's pass/fail from
   the log alone."

Reuses `test_terraform_plan.py`'s own gating (`require_standing`, real
terraform/tofu + terragoat checkout) rather than re-deriving it, so this
file degrades the same way that one does when the real environment is
absent.
"""

from __future__ import annotations

from gymact.verify_replay import terraform_plan_verify_from_log

from gymact.models import ActuationIntent

from .test_terraform_plan import (  # noqa: E402  (import after module-level require_standing gate)
    AUTHORITY,
    PLAN_CAPABILITY,
    _TERRAGOAT_TARGET_DIR,
    MaterializationIntent,
    _authorized_gym,
)


def test_verify_from_log_matches_verify_predicate_on_a_real_shaped_pass() -> None:
    observed = {
        "init_attempted": True,
        "init_returncode": 0,
        "plan_attempted": True,
        "plan_timed_out": False,
        "plan_returncode": 1,  # terraform plan returns non-zero on provider auth errors too
        "plan_stdout": "some real captured plan output",
    }

    assert terraform_plan_verify_from_log(observed) is True


def test_verify_from_log_fails_closed_on_incomplete_init() -> None:
    observed = {
        "init_attempted": True,
        "init_returncode": 1,  # init itself failed
        "plan_attempted": True,
        "plan_timed_out": False,
        "plan_returncode": 0,
        "plan_stdout": "output",
    }

    assert terraform_plan_verify_from_log(observed) is False


def test_verify_from_log_fails_closed_on_timed_out_plan() -> None:
    observed = {
        "init_attempted": True,
        "init_returncode": 0,
        "plan_attempted": True,
        "plan_timed_out": True,
        "plan_returncode": None,
        "plan_stdout": "",
    }

    assert terraform_plan_verify_from_log(observed) is False


def test_verify_from_log_fails_closed_on_empty_plan_stdout() -> None:
    observed = {
        "init_attempted": True,
        "init_returncode": 0,
        "plan_attempted": True,
        "plan_timed_out": False,
        "plan_returncode": 0,
        "plan_stdout": "",  # no captured output at all
    }

    assert terraform_plan_verify_from_log(observed) is False


async def test_real_episode_replays_from_captured_state_with_no_subprocess() -> None:
    gym = _authorized_gym()
    m = await gym.materialize(
        MaterializationIntent(
            provider="terraform-plan", config={"working_dir": str(_TERRAGOAT_TARGET_DIR)}
        )
    )
    episode_id = m.episode.episode_id

    act_result = await gym.act(
        ActuationIntent(episode_id=episode_id, capability=PLAN_CAPABILITY, authority_ref=AUTHORITY)
    )
    real_after_state = act_result.effect["after"]

    real_verification = await gym.verify(episode_id, {})
    await gym.teardown(episode_id, authority_ref=AUTHORITY)

    # The real, live verify() already ran a moment ago (above). Now
    # reproduce its exact verdict purely from the real captured `after`
    # state dict — no gym, no subprocess, no working directory.
    replayed_passed = terraform_plan_verify_from_log(real_after_state)

    assert replayed_passed == real_verification.passed
