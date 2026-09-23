"""Gate-free shared fixtures for the real terraform-plan court.

This module exists because `tests/test_terraform_plan.py` gates its whole
module through `gymact.standing.require_standing` (and a structural
parseability skip). Any name defined *after* those gates -- including plain
constants like `AUTHORITY` -- disappears whenever the gate fires, and any
other module that lazily imports such a name then dies with
``ImportError: cannot import name 'AUTHORITY'`` even when that other
module's own tests never need the real terraform collaborator. That was
GYMACT-5: one environment gate aborted collection of unrelated tests.

The contract here is intentionally narrow:

- Everything in this module is importable in every environment. Nothing at
  module scope probes the environment, raises, or skips.
- The gate itself (``require_standing`` for the environment-fixable gap,
  the unconditional named skip for the structural gap) lives in
  ``gate_real_terraform_environment()``. Callers choose where to apply it:
  `test_terraform_plan.py` applies it at module import (its documented
  whole-module contract); `test_verify_replay.py` applies it inside the one
  real end-to-end test that actually drives terraform, so its pure replay
  falsifiers stay independent of the terraform environment.
- The parseability probe runs a real ``init -backend=false`` subprocess and
  is memoized so the two callers share one observation instead of racing
  two identical inits into the same checkout.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from gymact import AllowListAuthorityResolver, GymAct
from gymact.gyms.terraform_plan import TerraformPlanProvider, resolve_binary
from gymact.standing import require_standing

TERRAGOAT_DIR = Path.home() / "autofde-lab" / "vendor" / "gyms" / "terragoat"
# terragoat's .tf files live under one subdirectory per cloud (aws/azure/gcp/
# alicloud), not at the repo root -- `terraform init` at the root would find
# zero .tf files and silently do nothing. Confirmed by real inspection this
# session (`find .../terragoat/*.tf` -> zero matches at root;
# `find .../terragoat/terraform/aws/*.tf` -> real files).
TERRAGOAT_TARGET_DIR = TERRAGOAT_DIR / "terraform" / "alicloud"
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

PLAN_CAPABILITY = "urn:gymact:terraform-plan:capability:plan"
# terraform_plan.py's requires_authority now defaults to True (a real
# terraform plan invocation must not run unauthorized) -- every act()-driving
# test below explicitly admits AUTHORITY.
AUTHORITY = "urn:test:terraform-plan-authority"


def terraform_binary_available() -> bool:
    return resolve_binary() is not None


def terragoat_checkout_present() -> tuple[bool, str]:
    """Environment-fixable gap: no clone, or binary missing. Gated through
    `require_standing()`'s opt-in mechanism -- the caller can un-degrade by
    fixing their environment (clone the submodule, install terraform/tofu)."""
    if not TERRAGOAT_TARGET_DIR.is_dir() or not any(TERRAGOAT_TARGET_DIR.glob("*.tf")):
        return False, f"{TERRAGOAT_TARGET_DIR} does not exist or has no .tf files"
    if resolve_binary() is None:
        return False, "neither 'terraform' nor 'tofu' is on PATH"
    return True, "ok"


def terragoat_parseable() -> tuple[bool, str]:
    """Real, not assumed: the repo being cloned is not sufficient evidence
    it's actually parseable by the installed terraform/tofu binary.

    A prior checkout of terragoat's `terraform/aws` used pre-0.12 legacy
    quoted type constraints (`type = "string"`), which no currently
    installable terraform/tofu version accepts -- a genuinely structural,
    non-environment-fixable incompatibility for that path (no local fix
    changes it; patching the vendored files would corrupt the pinned
    checkout). This test targets `terraform/alicloud` instead, which has no
    such legacy syntax and no remote backend block, and is confirmed real
    `init`-able below. If a future re-pin of the vendored checkout
    regresses `terraform/alicloud` to a similarly unparseable state, this
    check reports the real reason and this test is skipped unconditionally
    (never gated behind the env var) since that would again be a structural
    incompatibility, not a transient one.

    The observation is memoized: probing runs a real `init -backend=false`
    subprocess, and both consuming courts must share one observation of the
    same pinned checkout rather than racing identical inits.
    """
    global _PARSEABLE_OBSERVATION
    if _PARSEABLE_OBSERVATION is not None:
        return _PARSEABLE_OBSERVATION
    _PARSEABLE_OBSERVATION = _probe_terragoat_parseable()
    return _PARSEABLE_OBSERVATION


_PARSEABLE_OBSERVATION: tuple[bool, str] | None = None


def _probe_terragoat_parseable() -> tuple[bool, str]:
    present, reason = terragoat_checkout_present()
    if not present:
        return False, reason
    binary = resolve_binary()
    assert binary is not None  # guaranteed by terragoat_checkout_present
    try:
        completed = subprocess.run(
            [binary, "init", "-backend=false", "-input=false"],
            cwd=str(TERRAGOAT_TARGET_DIR),
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


def gate_real_terraform_environment(*, module_level: bool = True) -> None:
    """Apply the terraform-plan standing gates exactly where the caller
    wants them.

    Raises through `require_standing` (hard failure unless the run consented
    via GYMACT_ALLOW_DEGRADED_STANDINGS) when the checkout/binary is
    missing, then skips when the pinned checkout is structurally
    unparseable -- the same two gates, in the same order, that
    `test_terraform_plan.py` has always applied at module scope. Call sites:
    module scope there (``module_level=True``, the default); inside the one
    real end-to-end terraform test in `test_verify_replay.py`
    (``module_level=False`` -- a consented or structural degradation skips
    only the calling test, never that module's pure replay falsifiers).
    """
    import pytest

    checkout_present, checkout_reason = terragoat_checkout_present()
    require_standing(
        "LOCAL_GYM:terraform-plan",
        available=checkout_present,
        reason=f"real, environment-fixable gap: {checkout_reason} "
        "(clone ~/autofde-lab's terragoat submodule; install terraform or tofu)",
        skip_module_level=module_level,
    )

    parseable, parseable_reason = terragoat_parseable()
    if not parseable:
        # NOT gated through require_standing()'s opt-in mechanism: unlike a
        # missing checkout/binary, a real HCL parse failure against the pinned
        # terragoat commit is not fixable by the local environment -- see
        # `terragoat_parseable`'s docstring. This is a real, named, visible
        # skip (never silent), just unconditional rather than requiring every
        # ordinary run to opt into tolerating a permanent incompatibility.
        pytest.skip(
            f"terragoat/alicloud structurally unparseable by the installed "
            f"terraform/tofu (not a transient gap): {parseable_reason}",
            allow_module_level=module_level,
        )


def authorized_gym() -> GymAct:
    gym = GymAct(authority_resolver=AllowListAuthorityResolver({AUTHORITY}))
    gym.register_provider(TerraformPlanProvider())
    return gym


__all__ = [
    "AUTHORITY",
    "PLAN_CAPABILITY",
    "TERRAGOAT_DIR",
    "TERRAGOAT_TARGET_DIR",
    "authorized_gym",
    "gate_real_terraform_environment",
    "terraform_binary_available",
    "terragoat_checkout_present",
    "terragoat_parseable",
]
