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

Shared environment probes, constants and the authorized-gym helper live in
`terraform_plan_support` -- gate-free, so sibling courts can import
`AUTHORITY` without tripping this module's standing gates (GYMACT-5: the
gates used to sit textually above those constants, so a fired gate also
removed them and a lazy cross-module import died with
`ImportError: cannot import name 'AUTHORITY'`). This module still applies
the gates itself, at module scope, exactly as before.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from gymact import GymAct, MaterializationIntent
from gymact.gyms.terraform_plan import TerraformPlanProvider, resolve_binary
from gymact.models import ActuationIntent, Consequence, Operation
from gymact.ocel import receipts_to_ocel, validate_ocel_log, write_ocel_log
from gymact.process import ConformanceChecker

from .terraform_plan_support import (
    AUTHORITY,
    PLAN_CAPABILITY,
    gate_real_terraform_environment,
)
from .terraform_plan_support import (
    TERRAGOAT_DIR as _TERRAGOAT_DIR,
)
from .terraform_plan_support import (
    TERRAGOAT_TARGET_DIR as _TERRAGOAT_TARGET_DIR,
)
from .terraform_plan_support import (
    authorized_gym as _authorized_gym,
)

gate_real_terraform_environment()


async def _run_real_terraform_episode() -> list:
    """One real episode: materialize (real `init`) -> act (real `plan`) ->
    teardown. There is no `apply`/`destroy` step anywhere in this
    trajectory."""
    gym = _authorized_gym()
    receipts = []

    materialization = await gym.materialize(
        MaterializationIntent(
            provider="terraform-plan", config={"working_dir": str(_TERRAGOAT_TARGET_DIR)}
        )
    )
    assert materialization.accepted is True
    receipts.append(materialization.receipt)
    episode_id = materialization.episode.episode_id

    result = await gym.act(
        ActuationIntent(episode_id=episode_id, capability=PLAN_CAPABILITY, authority_ref=AUTHORITY)
    )
    assert result.accepted is True
    receipts.append(result.receipt)

    receipts.append(await gym.teardown(episode_id, authority_ref=AUTHORITY))
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
    gym = _authorized_gym()
    m = await gym.materialize(
        MaterializationIntent(
            provider="terraform-plan", config={"working_dir": str(_TERRAGOAT_TARGET_DIR)}
        )
    )
    episode_id = m.episode.episode_id

    result = await gym.act(
        ActuationIntent(episode_id=episode_id, capability=PLAN_CAPABILITY, authority_ref=AUTHORITY)
    )
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

    await gym.teardown(episode_id, authority_ref=AUTHORITY)


async def test_terraform_plan_provider_exposes_exactly_one_do_capability_named_plan() -> None:
    """Structural proof there is no apply/destroy capability to call.

    Two capabilities are exposed (`plan`, DO; `graph`, READ) -- the actual
    safety invariant this test guards is narrower than "exactly one
    capability total": no binding named `apply`/`destroy` exists, and
    exactly one DO-consequence capability exists (`plan` itself; `graph`
    is READ and can never mutate world state or consult a provider).
    """
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
    do_capabilities = [c for c in capabilities if c.consequence == Consequence.DO]
    assert len(do_capabilities) == 1
    assert do_capabilities[0].binding == "plan"
    assert do_capabilities[0].iri == PLAN_CAPABILITY
    bindings = {c.binding for c in capabilities}
    assert "apply" not in bindings
    assert "destroy" not in bindings

    await gym.teardown(episode_id)


async def test_terraform_graph_succeeds_where_plan_cannot_reach_provider_auth() -> None:
    """`graph` is a pure static analysis over local HCL -- it never contacts
    a provider, so it must succeed and enumerate real resource addresses
    even against a directory whose provider config makes `plan` fail
    before it can enumerate anything (real, deterministic case: terragoat's
    `terraform/alicloud`, whose provider requires a real `auth_type` that
    is absent in this environment on purpose -- no real cloud credentials
    are ever supplied to this test suite).

    `graph` is computed once, real, at materialize time -- not an
    `act()`-dispatchable capability (it is READ, and the kernel structurally
    refuses any non-DO capability passed to `act()`) -- so its evidence is
    read directly via `gym.observe()`, no separate actuation call needed.
    """
    alicloud_dir = _TERRAGOAT_DIR / "terraform" / "alicloud"
    if not alicloud_dir.is_dir() or not any(alicloud_dir.glob("*.tf")):
        pytest.skip(f"{alicloud_dir} does not exist or has no .tf files")
    if resolve_binary() is None:
        pytest.skip("neither 'terraform' nor 'tofu' is on PATH")

    gym = GymAct()
    gym.register_provider(TerraformPlanProvider())
    m = await gym.materialize(
        MaterializationIntent(provider="terraform-plan", config={"working_dir": str(alicloud_dir)})
    )
    episode_id = m.episode.episode_id

    observed = await gym.observe(episode_id)
    assert observed.state["graph_attempted"] is True
    assert observed.state["graph_returncode"] == 0
    assert observed.state["graph_timed_out"] is False

    graph_stdout = observed.state["graph_stdout"]
    for resource in (
        "alicloud_oss_bucket.bad_bucket",
        "alicloud_actiontrail_trail.fail",
        "alicloud_db_instance.seeme",
    ):
        assert resource in graph_stdout, graph_stdout

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


async def test_materialize_rejects_missing_or_wrong_typed_config() -> None:
    """Real validation errors from `TerraformPlanProvider.materialize`, no
    mocking involved -- each case is a genuinely malformed config dict."""
    provider = TerraformPlanProvider()

    with pytest.raises(TypeError, match="working_dir"):
        await provider.materialize(scenario=None, config={})

    with pytest.raises(ValueError, match="does not exist"):
        await provider.materialize(
            scenario=None, config={"working_dir": "/definitely/not/a/real/path/xyz"}
        )

    with pytest.raises(TypeError, match="binary"):
        await provider.materialize(
            scenario=None,
            config={"working_dir": str(_TERRAGOAT_TARGET_DIR), "binary": 12345},
        )

    with pytest.raises(TypeError, match="init_timeout_seconds"):
        await provider.materialize(
            scenario=None,
            config={
                "working_dir": str(_TERRAGOAT_TARGET_DIR),
                "init_timeout_seconds": "not-a-number",
            },
        )

    with pytest.raises(TypeError, match="requires_authority"):
        await provider.materialize(
            scenario=None,
            config={"working_dir": str(_TERRAGOAT_TARGET_DIR), "requires_authority": "yes"},
        )


async def test_actuate_rejects_an_unsupported_binding() -> None:
    """Structural proof (real call, real exception): there is no dispatch
    branch for anything other than `plan`, in particular not `apply`."""
    from gymact.models import Capability, Consequence

    gym = GymAct()
    gym.register_provider(TerraformPlanProvider())
    m = await gym.materialize(
        MaterializationIntent(
            provider="terraform-plan", config={"working_dir": str(_TERRAGOAT_TARGET_DIR)}
        )
    )
    episode_id = m.episode.episode_id
    env = gym._episodes[episode_id].environment

    bogus_apply = Capability(
        iri="urn:gymact:terraform-plan:capability:apply",
        title="not a real capability -- structurally rejected",
        consequence=Consequence.DO,
        binding="apply",
    )
    with pytest.raises(ValueError, match="unsupported terraform-plan binding"):
        await env.actuate(bogus_apply, {})

    await gym.teardown(episode_id)


async def test_environment_checkpoint_and_restore_round_trip_real_state() -> None:
    gym = GymAct()
    gym.register_provider(TerraformPlanProvider())
    m = await gym.materialize(
        MaterializationIntent(
            provider="terraform-plan", config={"working_dir": str(_TERRAGOAT_TARGET_DIR)}
        )
    )
    episode_id = m.episode.episode_id
    env = gym._episodes[episode_id].environment

    checkpoint = await env.checkpoint()
    assert checkpoint["init_attempted"] is True

    await env.actuate(env.capabilities()[0], {})
    observed_after_plan = await env.observe()
    assert observed_after_plan["plan_attempted"] is True

    await env.restore(checkpoint)
    restored = await env.observe()
    assert restored["plan_attempted"] is False

    await gym.teardown(episode_id)


async def test_resolve_binary_prefers_explicit_argument_and_falls_back_to_path() -> None:
    # A real, genuinely nonexistent preferred binary must fall through to a
    # real PATH lookup rather than being returned as-is.
    fallback = resolve_binary("definitely-not-a-real-binary-xyz")
    assert fallback in {"terraform", "tofu"} or fallback is None or "/" in (fallback or "")

    real_binary = resolve_binary()
    assert real_binary is not None  # guaranteed by require_standing gate above
    # A real, installed binary passed explicitly as `preferred` is returned
    # directly (first candidate tried).
    preferred_name = Path(real_binary).name
    assert resolve_binary(preferred_name) is not None


async def test_real_terraform_plan_timeout_is_captured_not_swallowed() -> None:
    """A real, unrealistically short timeout against a real `terraform plan`
    invocation reliably trips `subprocess.TimeoutExpired` -- exercises the
    real timeout-handling branch without mocking `subprocess`."""
    gym = _authorized_gym()
    m = await gym.materialize(
        MaterializationIntent(
            provider="terraform-plan",
            config={
                "working_dir": str(_TERRAGOAT_TARGET_DIR),
                "plan_timeout_seconds": 0.001,
            },
        )
    )
    episode_id = m.episode.episode_id

    result = await gym.act(
        ActuationIntent(episode_id=episode_id, capability=PLAN_CAPABILITY, authority_ref=AUTHORITY)
    )
    after = result.effect["after"]
    assert after["plan_attempted"] is True
    assert after["plan_timed_out"] is True
    assert after["plan_returncode"] is None

    await gym.teardown(episode_id, authority_ref=AUTHORITY)


async def test_real_init_against_a_nonexistent_binary_path_surfaces_an_oserror() -> None:
    """A real, nonexistent binary path makes `subprocess.run` raise a real
    `FileNotFoundError` (an `OSError` subclass) -- exercises the real OSError
    branch in `materialize_real_init`/`actuate`, no mocking of `subprocess`."""
    from gymact.gyms.terraform_plan import TerraformPlanEnvironment

    env = TerraformPlanEnvironment(
        binary="/definitely/not/a/real/binary/xyz",
        working_dir=str(_TERRAGOAT_TARGET_DIR),
        init_timeout_seconds=30.0,
        plan_timeout_seconds=30.0,
    )
    state = await env.materialize_real_init()
    assert state["init_attempted"] is True
    assert state["init_returncode"] is None
    assert state["init_stderr"] != ""

    result = await env.actuate(env.capabilities()[0], {})
    assert result["after"]["plan_attempted"] is True
    assert result["after"]["plan_returncode"] is None
