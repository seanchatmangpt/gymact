"""Chicago-style tests for `gymact.verify_replay` —
`docs/jira/v26.8.12/cloud-cert-wbpr-prd.md` FR4, Terraform proof of concept.

The pure replay predicates collect and execute without Terraform.  The one
real end-to-end replay proof imports the Terraform court lazily, so that
court's explicit environment/structural skip remains a skip for the real
integration test rather than aborting collection of these independent pure
replay falsifiers.
"""

from __future__ import annotations

from gymact.models import ActuationIntent, MaterializationIntent
from gymact.verify_replay import terraform_plan_verify_from_log

from .terraform_plan_support import (
    AUTHORITY,
    PLAN_CAPABILITY,
    TERRAGOAT_TARGET_DIR,
    authorized_gym,
    gate_real_terraform_environment,
)


def test_verify_from_log_matches_verify_predicate_on_a_real_shaped_pass() -> None:
    observed = {
        "init_attempted": True,
        "init_returncode": 0,
        "plan_attempted": True,
        "plan_timed_out": False,
        "plan_returncode": 1,
        "plan_stdout": "some real captured plan output",
    }
    assert terraform_plan_verify_from_log(observed) is True


def test_verify_from_log_fails_closed_on_incomplete_init() -> None:
    observed = {
        "init_attempted": True,
        "init_returncode": 1,
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
        "plan_stdout": "",
    }
    assert terraform_plan_verify_from_log(observed) is False


async def test_real_episode_replays_from_captured_state_with_no_subprocess() -> None:
    # The one real integration boundary.  The standing gates (consented skip
    # or hard failure for the environment-fixable gap; named skip for the
    # structural gap) apply HERE, scoped to this test only: the pure replay
    # falsifiers above stay collectable and meaningful without terraform.
    # GYMACT-5: this used to lazily import its fixtures out of
    # test_terraform_plan's gated module scope, so a fired gate also removed
    # AUTHORITY and the import died with `cannot import name 'AUTHORITY'`.
    gate_real_terraform_environment(module_level=False)

    gym = authorized_gym()
    m = await gym.materialize(
        MaterializationIntent(
            provider="terraform-plan", config={"working_dir": str(TERRAGOAT_TARGET_DIR)}
        )
    )
    episode_id = m.episode.episode_id

    act_result = await gym.act(
        ActuationIntent(episode_id=episode_id, capability=PLAN_CAPABILITY, authority_ref=AUTHORITY)
    )
    real_after_state = act_result.effect["after"]

    real_verification = await gym.verify(episode_id, {})
    await gym.teardown(episode_id, authority_ref=AUTHORITY)

    replayed_passed = terraform_plan_verify_from_log(real_after_state)
    assert replayed_passed == real_verification.passed
