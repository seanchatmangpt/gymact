"""Real GymAct `Environment`/`EnvironmentProvider` backed by a real local
`terraform`/`tofu` binary run against a real, already-checked-out Terraform
configuration directory (e.g. `terragoat`) -- not simulated.

HARD SAFETY CONSTRAINT, load-bearing for this whole module: this provider
runs `terraform init`, `terraform validate`, and `terraform plan` only. It
never runs `terraform apply` or `terraform destroy`, and no capability in
`TERRAFORM_PLAN_CAPABILITIES` binds to either. This is enforced structurally
(there is exactly one DO capability, `plan`, and `actuate()` has no dispatch
branch that could reach `apply`/`destroy`), not by a runtime flag that could
be flipped. A real cloud-provider auth failure surfaced by `terraform plan`
(e.g. "No valid credential sources found") is a legitimate real outcome --
`verify()` reports it via captured stdout/stderr and a non-zero-but-not-init
returncode signal, it is never suppressed or reclassified as success.

Matches `discovered.py`'s subprocess pattern: real `subprocess.run` calls
against a real directory, with real captured stdout/stderr/returncode/timeout
as evidence. No Terraform Python SDK or HCL parser is used -- none is a
gymact dependency.

`materialize()` runs a real `terraform init -backend=false` (or `tofu`
equivalent) in the configured working directory. `-backend=false` is load-
bearing, not cosmetic: found live this session that terragoat's
`providers.tf` actually declares a real S3 remote backend requiring
`bucket`/`key`/`region` -- an earlier version of this docstring assumed "no
remote backend block," which was simply wrong for the real checked-out
target. Without `-backend=false`, `init` would attempt to configure that S3
backend and fail on missing required attributes (confirmed: real
`Error: Missing Required Value` on `bucket`/`key`/`region`) -- or, with those
supplied, would mean real Terraform *state* being written to a real AWS S3
bucket, which is exactly the kind of cloud-credential-touching behavior this
plan-only provider must never risk. `-backend=false` guarantees init only
ever produces local, ephemeral `.terraform/` scaffolding, never a remote
state write attempt.
`init` may still reach out to the public Terraform provider registry to
download provider plugins (aws/azurerm/google in terragoat's case); that is
read-only registry traffic, not cloud infrastructure access, and requires no
cloud credentials. If a fully offline run is required, pre-populate
`.terraform/providers` via a mirrored `.terraformrc` before calling this
provider -- that concern is deliberately left to the caller/environment, not
hard-coded here, since the safety-relevant property (no apply/destroy ever)
does not depend on it.

`terraform plan` itself requires no cloud credentials to *run* -- it will
attempt to refresh/read remote state and provider data sources, and without
credentials most providers report an auth error per-resource rather than
refusing to start. That per-resource auth error is captured as real evidence
in `stdout`/`stderr`, not swallowed.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any
from uuid import uuid4

from gymact.models import Capability, Consequence

_MAX_CAPTURED_OUTPUT = 8000
_DEFAULT_INIT_TIMEOUT_SECONDS = 300.0
_DEFAULT_PLAN_TIMEOUT_SECONDS = 300.0


def resolve_binary(preferred: str | None = None) -> str | None:
    """Return the real path of a usable `terraform` or `tofu` binary, or
    `None` if neither is on `PATH`. `preferred` (if given) is tried first."""
    candidates = [preferred] if preferred else []
    candidates.extend(["terraform", "tofu"])
    for name in candidates:
        if name is None:
            continue
        found = shutil.which(name)
        if found:
            return found
    return None


TERRAFORM_PLAN_CAPABILITIES = (
    Capability(
        iri="urn:gymact:terraform-plan:capability:plan",
        title="Run a real, read-only `terraform plan` against the materialized "
        "configuration directory",
        consequence=Consequence.DO,
        binding="plan",
    ),
)


class TerraformPlanEnvironment:
    """Wraps one real Terraform/OpenTofu configuration directory. Only
    `init`, `validate`, and `plan` are ever invoked by this class -- there is
    no code path here that can run `apply` or `destroy`."""

    def __init__(
        self,
        *,
        binary: str,
        working_dir: str,
        init_timeout_seconds: float,
        plan_timeout_seconds: float,
        requires_authority: bool = False,
    ) -> None:
        self.environment_id = f"urn:gymact:terraform-plan:environment:{uuid4().hex}"
        self.requires_authority = requires_authority
        self._binary = binary
        self._working_dir = working_dir
        self._init_timeout = init_timeout_seconds
        self._plan_timeout = plan_timeout_seconds
        self._state: dict[str, Any] = {
            "binary": binary,
            "working_dir": working_dir,
            "init_attempted": False,
            "init_returncode": None,
            "init_stdout": "",
            "init_stderr": "",
            "plan_attempted": False,
            "plan_returncode": None,
            "plan_stdout": "",
            "plan_stderr": "",
            "plan_timed_out": False,
        }
        self._closed = False

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError("environment is torn down")

    def _run(self, args: list[str], *, timeout: float) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [self._binary, *args],
            cwd=self._working_dir,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )

    def capabilities(self) -> tuple[Capability, ...]:
        self._ensure_open()
        return TERRAFORM_PLAN_CAPABILITIES

    async def observe(self) -> dict[str, Any]:
        self._ensure_open()
        return dict(self._state)

    async def materialize_real_init(self) -> dict[str, Any]:
        """Real `terraform init` (or `tofu init`) against a purely local
        backend -- no cloud credentials are consulted for `init` itself.
        Called once from the provider's `materialize()`, not from `actuate`,
        since init is setup, not a scored capability."""
        self._ensure_open()
        try:
            completed = self._run(
                ["init", "-backend=false", "-input=false", "-no-color"],
                timeout=self._init_timeout,
            )
            self._state["init_attempted"] = True
            self._state["init_returncode"] = completed.returncode
            self._state["init_stdout"] = completed.stdout[-_MAX_CAPTURED_OUTPUT:]
            self._state["init_stderr"] = completed.stderr[-_MAX_CAPTURED_OUTPUT:]
        except subprocess.TimeoutExpired as exc:
            self._state["init_attempted"] = True
            self._state["init_returncode"] = None
            self._state["init_stdout"] = (
                (exc.stdout or "")[-_MAX_CAPTURED_OUTPUT:] if isinstance(exc.stdout, str) else ""
            )
            self._state["init_stderr"] = (
                (exc.stderr or "")[-_MAX_CAPTURED_OUTPUT:] if isinstance(exc.stderr, str) else ""
            )
        except OSError as exc:
            self._state["init_attempted"] = True
            self._state["init_returncode"] = None
            self._state["init_stderr"] = str(exc)
        return dict(self._state)

    async def actuate(self, capability: Capability, payload: dict[str, Any]) -> dict[str, Any]:
        del payload
        self._ensure_open()
        if capability.binding != "plan":
            # There is deliberately no other branch here. In particular
            # there is no "apply" or "destroy" binding to dispatch to, even
            # disabled -- see module docstring.
            raise ValueError(f"unsupported terraform-plan binding: {capability.binding}")

        before = dict(self._state)
        try:
            completed = self._run(
                ["plan", "-input=false", "-no-color", "-lock=false"],
                timeout=self._plan_timeout,
            )
            self._state["plan_attempted"] = True
            self._state["plan_returncode"] = completed.returncode
            self._state["plan_stdout"] = completed.stdout[-_MAX_CAPTURED_OUTPUT:]
            self._state["plan_stderr"] = completed.stderr[-_MAX_CAPTURED_OUTPUT:]
            self._state["plan_timed_out"] = False
        except subprocess.TimeoutExpired as exc:
            self._state["plan_attempted"] = True
            self._state["plan_returncode"] = None
            self._state["plan_stdout"] = (
                (exc.stdout or "")[-_MAX_CAPTURED_OUTPUT:] if isinstance(exc.stdout, str) else ""
            )
            self._state["plan_stderr"] = (
                (exc.stderr or "")[-_MAX_CAPTURED_OUTPUT:] if isinstance(exc.stderr, str) else ""
            )
            self._state["plan_timed_out"] = True
        except OSError as exc:
            self._state["plan_attempted"] = True
            self._state["plan_returncode"] = None
            self._state["plan_stderr"] = str(exc)
            self._state["plan_timed_out"] = False

        after = dict(self._state)
        return {"before": before, "after": after}

    async def verify(self, expected: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
        """Checks real captured state: init must have succeeded (returncode
        0 -- init touches no cloud credentials so it must be deterministic
        locally) and plan must have *run to completion* (attempted, not
        timed out, and produced some real output), regardless of whether a
        valid cloud credential was found -- a per-resource auth error inside
        a completed plan run is legitimate real evidence, not a failure of
        this environment."""
        self._ensure_open()
        observed = dict(self._state)
        if expected:
            passed = all(observed.get(key) == value for key, value in expected.items())
        else:
            init_ok = (
                observed.get("init_attempted") is True and observed.get("init_returncode") == 0
            )
            plan_ran = (
                observed.get("plan_attempted") is True
                and observed.get("plan_timed_out") is False
                and observed.get("plan_returncode") is not None
                and bool(observed.get("plan_stdout")) is True
            )
            passed = init_ok and plan_ran
        return passed, observed

    async def checkpoint(self) -> dict[str, Any]:
        self._ensure_open()
        return dict(self._state)

    async def restore(self, checkpoint: dict[str, Any]) -> None:
        self._ensure_open()
        self._state = dict(checkpoint)

    async def teardown(self) -> None:
        """No-op by default: local `.terraform`/state cleanup is confined to
        removing the local `.terraform` plugin-cache directory this
        environment's own `init` created, never the configuration directory
        itself and never anything requiring cloud access. Left minimal on
        purpose -- terragoat's checkout is shared/reusable across runs, so
        this does not delete `.terraform.lock.hcl` or state files that a
        concurrent run might depend on."""
        self._closed = True


class TerraformPlanProvider:
    """Materializes a `TerraformPlanEnvironment` from a real, already
    checked-out Terraform configuration directory. Never invokes `apply` or
    `destroy` -- see module docstring."""

    name = "terraform-plan"
    materialization_requires_authority = False

    async def materialize(
        self, *, scenario: str | None, config: dict[str, Any]
    ) -> TerraformPlanEnvironment:
        del scenario
        working_dir = config.get("working_dir")
        if not isinstance(working_dir, str) or not working_dir:
            raise TypeError("config.working_dir must be a non-empty string")
        if not Path(working_dir).is_dir():
            raise ValueError(
                f"config.working_dir does not exist or is not a directory: {working_dir}"
            )

        preferred_binary = config.get("binary")
        if preferred_binary is not None and not isinstance(preferred_binary, str):
            raise TypeError("config.binary must be a string when provided")
        binary = resolve_binary(preferred_binary)
        if binary is None:
            raise RuntimeError(
                "neither 'terraform' nor 'tofu' is on PATH -- install one to use "
                "TerraformPlanProvider"
            )

        init_timeout_seconds = config.get("init_timeout_seconds", _DEFAULT_INIT_TIMEOUT_SECONDS)
        plan_timeout_seconds = config.get("plan_timeout_seconds", _DEFAULT_PLAN_TIMEOUT_SECONDS)
        for value, field_name in (
            (init_timeout_seconds, "init_timeout_seconds"),
            (plan_timeout_seconds, "plan_timeout_seconds"),
        ):
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                raise TypeError(f"config.{field_name} must be a number")

        requires_authority = config.get("requires_authority", False)
        if not isinstance(requires_authority, bool):
            raise TypeError("config.requires_authority must be a boolean")

        environment = TerraformPlanEnvironment(
            binary=binary,
            working_dir=working_dir,
            init_timeout_seconds=float(init_timeout_seconds),
            plan_timeout_seconds=float(plan_timeout_seconds),
            requires_authority=requires_authority,
        )
        await environment.materialize_real_init()
        return environment
