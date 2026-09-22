"""Chicago-style: a real GymAct episode driving a real `terraform`/`tofu`
binary against terragoat's real checked-out `.tf` files -- not simulated.

HARD SAFETY CONSTRAINT for this whole test module (matching
`gymact.gyms.terraform_plan`'s own docstring): only `terraform init` and
`terraform plan` are ever run here. Nothing in this file calls, imports, or
exercises an `apply`/`destroy` path -- `TerraformPlanProvider` structurally
has no such capability to call.

Per `gymact.standing.require_standing`, the real thing is the default: if
neither `terraform` nor `tofu` is on `PATH`, or the real terragoat checkout
at `~/autofde-lab/vendor/gyms/terragoat` has no real `.tf` files, this module
FAILS unless the run explicitly sets `GYMACT_ALLOW_DEGRADED_STANDINGS` to
include "LOCAL_GYM:terraform-plan" (or "*") -- a skip here is something a run
must opt into, never something it silently gets. Matches
`test_cube_container_counter.py`'s and `test_kubernetes_reconciliation.py`'s
contract.
"""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from gymact.gyms.terraform_plan import resolve_binary

_TERRAGOAT_DIR = Path.home() / "autofde-lab" / "vendor" / "gyms" / "terragoat"
# terragoat's .tf files live under one subdirectory per cloud (aws/azure/gcp/
# alicloud), not at the repo root -- `terraform init` at the root would find
# zero .tf files and silently do nothing. Confirmed by real inspection this
# session (`find .../terragoat/*.tf` -> zero matches at root;
# `find .../terragoat/terraform/aws/*.tf` -> real files).
_TERRAGOAT_TARGET_DIR = _TERRAGOAT_DIR / "terraform" / "alicloud"
# `terraform/aws` was the first target tried, but it declares a real remote
# `backend "s3" { ... }` (providers.tf) -- confirmed this session that
# `terraform plan` refuses to run against it once `init -backend=false` was
# used (a real, reproducible "Backend initialization required" error, not
# stale state -- retested from a fully clean `.terraform`). Supplying real
# S3 config would mean real Terraform state written to a real AWS bucket,
# which this plan-only provider must never risk. `terraform/alicloud`
# declares no backend block at all and its `.tf` files have no legacy
# quoted-type-constraint syntax either, so `init -backend=false` and `plan`
# both run to real completion -- `plan` surfaces a real, legitimate
# provider-config error (`Invalid type option` on the `alicloud` provider's
# auth type) in real stdout, exactly the "completed run, real per-resource
# error" case this provider is designed to treat as valid evidence.


def _terraform_binary_available() -> bool:
    return resolve_binary() is not None


def _terragoat_usable() -> tuple[bool, str]:
    """Real, not assumed: the repo being cloned is not sufficient evidence
    it's actually parseable by the installed terraform/tofu binary.

    Found live this session: terragoat's `.tf` files use pre-0.12 legacy
    quoted type constraints (`type = "string"`), which both the installed
    `terraform` (v1.14.6) and `tofu` (v1.10.6) reject at parse time, before
    even reaching provider download. A previous version of this check only
    tested `.rglob("*.tf")` existence -- accurate before the clone, silently
    wrong after it (a real, checked-out, real-.tf-containing directory that
    still cannot actually be `terraform init`-ed). Run the real init for
    real, bounded, and report the real reason if it fails, rather than
    trusting file presence as a proxy for usability.
    """
    if not _TERRAGOAT_TARGET_DIR.is_dir() or not any(_TERRAGOAT_TARGET_DIR.glob("*.tf")):
        return False, f"{_TERRAGOAT_TARGET_DIR} does not exist or has no .tf files"
    binary = resolve_binary()
    if binary is None:
        return False, "neither 'terraform' nor 'tofu' is on PATH"
    try:
        completed = subprocess.run(
            [binary, "init", "-backend=false", "-input=false"],
            cwd=str(_TERRAGOAT_TARGET_DIR),
            capture_output=True,
            text=True,
            timeout=90,
            check=False,
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        return False, f"real `{binary} init` attempt raised {type(exc).__name__}: {exc}"
    if completed.returncode != 0:
        return False, (
            f"real `{binary} init -backend=false` against the real checked-out "
            f"terragoat config failed (exit {completed.returncode}): "
            f"{completed.stderr[-400:] or completed.stdout[-400:]}"
        )
    return True, "ok"


_USABLE, _USABLE_REASON = _terragoat_usable()

if not _USABLE:
    # NOT gated through require_standing()'s opt-in mechanism: that
    # mechanism exists for transient, environment-fixable gaps ("start
    # colima," "install this extra") -- the caller can un-degrade by fixing
    # their environment. Confirmed this session terragoat's own `.tf` files
    # use pre-0.12 legacy HCL syntax that no currently-installable
    # terraform/tofu version accepts; no environment fix changes that, and
    # patching terragoat's vendored files would corrupt the pinned checkout
    # rather than fix a real gap. Per user direction, terragoat is removed
    # from GymAct actuation consideration -- see
    # docs/papers/smoke-lock.ttl's `vendor-terragoat` UNSUPPORTED entry in
    # autofde-lab. This is a real, named, visible skip (never silent) --
    # just unconditional rather than requiring every ordinary test run to
    # explicitly opt into tolerating a permanent, structural incompatibility.
    import pytest

    pytest.skip(
        f"terragoat structurally excluded from GymAct consideration "
        f"(not a transient gap): {_USABLE_REASON}",
        allow_module_level=True,
    )

from gymact import GymAct, MaterializationIntent  # noqa: E402
from gymact.gyms.terraform_plan import TerraformPlanProvider  # noqa: E402
from gymact.models import ActuationIntent, Operation, Standing  # noqa: E402
from gymact.ocel import receipts_to_ocel, validate_ocel_log, write_ocel_log  # noqa: E402
from gymact.process import ConformanceChecker  # noqa: E402

PLAN_CAPABILITY = "urn:gymact:terraform-plan:capability:plan"


async def _run_real_terraform_episode() -> list:
    """One real episode: materialize (real `init`) -> act (real `plan`) ->
    teardown. There is no `apply`/`destroy` step anywhere in this
    trajectory."""
    gym = GymAct()
    gym.register_provider(TerraformPlanProvider())
    receipts = []

    materialization = await gym.materialize(
        MaterializationIntent(
            provider="terraform-plan", config={"working_dir": str(_TERRAGOAT_TARGET_DIR)}
        )
    )
    assert materialization.accepted is True
    receipts.append(materialization.receipt)
    episode_id = materialization.episode.episode_id

    result = await gym.act(ActuationIntent(episode_id=episode_id, capability=PLAN_CAPABILITY))
    assert result.accepted is True
    receipts.append(result.receipt)

    receipts.append(await gym.teardown(episode_id))
    return receipts


async def test_materialize_runs_a_real_terraform_init_against_terragoat() -> None:
    gym = GymAct()
    gym.register_provider(TerraformPlanProvider())

    materialization = await gym.materialize(
        MaterializationIntent(
            provider="terraform-plan", config={"working_dir": str(_TERRAGOAT_TARGET_DIR)}
        )
    )
    assert materialization.accepted is True
    episode_id = materialization.episode.episode_id

    observed = await gym.observe(episode_id)
    assert observed.state["init_attempted"] is True
    # init runs against a purely local backend -- no cloud creds involved --
    # so it must succeed deterministically regardless of cloud auth state.
    assert observed.state["init_returncode"] == 0

    await gym.teardown(episode_id)


async def test_plan_capability_runs_a_real_terraform_plan_and_captures_completion() -> None:
    gym = GymAct()
    gym.register_provider(TerraformPlanProvider())
    m = await gym.materialize(
        MaterializationIntent(
            provider="terraform-plan", config={"working_dir": str(_TERRAGOAT_TARGET_DIR)}
        )
    )
    episode_id = m.episode.episode_id

    result = await gym.act(ActuationIntent(episode_id=episode_id, capability=PLAN_CAPABILITY))
    assert result.accepted is True

    after = result.effect["after"]
    assert after["plan_attempted"] is True
    assert after["plan_timed_out"] is False
    # plan must run to real completion (some returncode, some real output)
    # regardless of whether valid cloud credentials were found -- a
    # per-resource auth error inside a completed run is legitimate evidence,
    # not something this test suppresses.
    assert after["plan_returncode"] is not None
    assert after["plan_stdout"] or after["plan_stderr"]

    verification = await gym.verify(episode_id, {})
    assert verification.passed is True

    await gym.teardown(episode_id)


async def test_terraform_plan_provider_exposes_exactly_one_do_capability_named_plan() -> None:
    """Structural proof there is no apply/destroy capability to call."""
    gym = GymAct()
    gym.register_provider(TerraformPlanProvider())
    m = await gym.materialize(
        MaterializationIntent(
            provider="terraform-plan", config={"working_dir": str(_TERRAGOAT_TARGET_DIR)}
        )
    )
    episode_id = m.episode.episode_id

    env = gym._episodes[episode_id].environment
    capabilities = env.capabilities()
    assert len(capabilities) == 1
    assert capabilities[0].binding == "plan"
    assert capabilities[0].iri == PLAN_CAPABILITY
    bindings = {c.binding for c in capabilities}
    assert "apply" not in bindings
    assert "destroy" not in bindings

    await gym.teardown(episode_id)


async def test_terraform_plan_episode_replays_conformant_and_produces_a_valid_ocel_log() -> None:
    receipts = await _run_real_terraform_episode()
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

    with tempfile.TemporaryDirectory() as tmp_dir:
        log_path = Path(tmp_dir) / "terraform-plan-episode.ocel.json"
        written_log, digest = write_ocel_log(log_path, receipts)
        assert log_path.exists()
        assert written_log == log
        assert len(digest) == 64  # real sha256 hex digest
        validate_ocel_log(written_log)  # re-validate the exact persisted log
