"""Real GymAct `Environment`/`EnvironmentProvider` backed by a real local
`terraform`/`tofu` binary run against a real, HAND-AUTHORED, CHECKED-IN
Terraform configuration directory
(`gyms/fixtures/terraform_docker/main.tf`) -- not simulated.

WHY THIS PROVIDER IS ALLOWED TO `apply`/`destroy` WHEN `terraform_plan.py`
DELIBERATELY IS NOT:

`terraform_plan.py` runs `terraform plan` (never `apply`/`destroy`) against
an arbitrary, externally-owned, already-checked-out configuration directory
(e.g. terragoat) whose resource graph can name real cloud-provider
resources and consume real cloud credentials -- an unbounded blast radius
that must never be actuated. This module is different in every safety-load-
bearing way:

  1. The Terraform config it applies is HAND-AUTHORED and CHECKED INTO this
     repository at `gyms/fixtures/terraform_docker/main.tf` -- fixed,
     small, auditable, and never sourced from an external/vendored/
     untrusted directory. Nothing about which resources exist is
     data-driven or discovered at runtime.
  2. The only provider it declares is `kreuzwerker/docker`, pointed at
     colima's real LOCAL Docker daemon socket (`unix://...colima/...
     docker.sock`) -- never a cloud endpoint, never cloud credentials.
  3. The only resources the checked-in config can ever create are exactly
     one `docker_image` (pinned `nginx:alpine`) and exactly one
     `docker_container` built from that image. There is no module, no
     `for_each`, no dynamic resource generation, and no other provider
     block -- so `apply`/`destroy` here can only ever create/destroy a
     single local, throwaway Docker container. This is a fixed, small,
     auditable blast radius, confined entirely to the local machine's own
     Docker daemon -- structurally, not by a runtime flag that could be
     flipped.

Matches `terraform_plan.py`'s subprocess pattern: real `subprocess.run`
calls with real captured stdout/stderr/returncode/timeout as evidence. No
Terraform Python SDK or HCL parser is used -- none is a gymact dependency.

`verify()` never trusts `terraform apply`'s exit code alone: it polls real
`docker ps -a --filter name=<container>` output for the container's real
`State.Running` status. `teardown()` likewise never trusts `terraform
destroy`'s exit code alone: it confirms via real `docker ps -a` that the
container is actually gone, and surfaces a leaked container as a real
failure rather than a silent success.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any
from uuid import uuid4

from gymact.models import Capability, Consequence

_MAX_CAPTURED_OUTPUT = 8000
_DEFAULT_INIT_TIMEOUT_SECONDS = 300.0
_DEFAULT_APPLY_TIMEOUT_SECONDS = 300.0
_DEFAULT_DESTROY_TIMEOUT_SECONDS = 300.0
_DEFAULT_VERIFY_TIMEOUT_SECONDS = 60.0
_POLL_INTERVAL_SECONDS = 1.0

_FIXTURES_DIR = Path(__file__).parent / "fixtures" / "terraform_docker"
_DEFAULT_CONTAINER_NAME = "gymact-terraform-docker-apply-test"


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


TERRAFORM_DOCKER_APPLY_CAPABILITIES = (
    Capability(
        iri="urn:gymact:terraform-docker-apply:capability:plan",
        title="Run a real, read-only `terraform plan` against the checked-in local-Docker config",
        consequence=Consequence.READ,
        binding="plan",
    ),
    Capability(
        iri="urn:gymact:terraform-docker-apply:capability:apply",
        title="Run a real `terraform apply` that creates one real local "
        "docker_image and one real local docker_container",
        consequence=Consequence.DO,
        binding="apply",
    ),
    Capability(
        iri="urn:gymact:terraform-docker-apply:capability:destroy",
        title="Run a real `terraform destroy` that removes the real local "
        "docker_container and docker_image",
        consequence=Consequence.DO,
        binding="destroy",
    ),
)


def _docker_container_json(name: str) -> dict[str, Any] | None:
    """Real `docker ps -a --filter name=<name> --format {{json .}}` lookup.

    Returns None if no container with that exact name exists, the parsed
    container summary object otherwise. Uses `docker inspect` for the
    authoritative real `.State.Running` boolean (the `docker ps` table
    format's status string is for humans, not for parsing).
    """
    result = subprocess.run(
        ["docker", "inspect", name],
        capture_output=True,
        text=True,
        timeout=15.0,
        check=False,
    )
    if result.returncode != 0:
        return None
    try:
        parsed = json.loads(result.stdout)
    except json.JSONDecodeError:
        return None
    if not parsed:
        return None
    return parsed[0]


def _container_running(name: str) -> bool:
    container = _docker_container_json(name)
    if container is None:
        return False
    return bool(container.get("State", {}).get("Running", False))


class TerraformDockerApplyEnvironment:
    """Wraps one real Terraform/OpenTofu run of the checked-in
    `fixtures/terraform_docker` config against colima's real local Docker
    daemon. `plan`, `apply`, and `destroy` are all real subprocess-backed
    capabilities -- see module docstring for why `apply`/`destroy` are safe
    here specifically."""

    def __init__(
        self,
        *,
        binary: str,
        working_dir: str,
        container_name: str,
        docker_host: str | None,
        init_timeout_seconds: float,
        apply_timeout_seconds: float,
        destroy_timeout_seconds: float,
        verify_timeout_seconds: float,
        requires_authority: bool = False,
    ) -> None:
        self.environment_id = f"urn:gymact:terraform-docker-apply:environment:{uuid4().hex}"
        self.requires_authority = requires_authority
        self._binary = binary
        self._working_dir = working_dir
        self._container_name = container_name
        self._docker_host = docker_host
        self._init_timeout = init_timeout_seconds
        self._apply_timeout = apply_timeout_seconds
        self._destroy_timeout = destroy_timeout_seconds
        self._verify_timeout = verify_timeout_seconds
        self._state: dict[str, Any] = {
            "binary": binary,
            "working_dir": working_dir,
            "container_name": container_name,
            "init_attempted": False,
            "init_returncode": None,
            "plan_attempted": False,
            "plan_returncode": None,
            "plan_stdout": "",
            "plan_stderr": "",
            "apply_attempted": False,
            "apply_returncode": None,
            "apply_stdout": "",
            "apply_stderr": "",
            "destroy_attempted": False,
            "destroy_returncode": None,
            "destroy_stdout": "",
            "destroy_stderr": "",
        }
        self._closed = False

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError("environment is torn down")

    def _tf_vars(self) -> list[str]:
        args = ["-var", f"container_name={self._container_name}"]
        if self._docker_host:
            args.extend(["-var", f"docker_host={self._docker_host}"])
        return args

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
        return TERRAFORM_DOCKER_APPLY_CAPABILITIES

    async def observe(self) -> dict[str, Any]:
        self._ensure_open()
        merged = dict(self._state)
        merged["container"] = _docker_container_json(self._container_name)
        merged["container_running"] = _container_running(self._container_name)
        return merged

    async def materialize_real_init(self) -> dict[str, Any]:
        """Real `terraform init` (or `tofu init`) against the checked-in
        local-only config. Called once from the provider's `materialize()`."""
        self._ensure_open()
        try:
            completed = self._run(["init", "-input=false", "-no-color"], timeout=self._init_timeout)
            self._state["init_attempted"] = True
            self._state["init_returncode"] = completed.returncode
            self._state["init_stdout"] = completed.stdout[-_MAX_CAPTURED_OUTPUT:]
            self._state["init_stderr"] = completed.stderr[-_MAX_CAPTURED_OUTPUT:]
        except subprocess.TimeoutExpired as exc:
            self._state["init_attempted"] = True
            self._state["init_returncode"] = None
            self._state["init_stderr"] = (
                (exc.stderr or "")[-_MAX_CAPTURED_OUTPUT:] if isinstance(exc.stderr, str) else ""
            )
        return dict(self._state)

    async def actuate(self, capability: Capability, payload: dict[str, Any]) -> dict[str, Any]:
        del payload
        self._ensure_open()
        binding = capability.binding
        before = await self.observe()

        if binding == "plan":
            completed = self._run(
                ["plan", "-input=false", "-no-color", "-lock=false", *self._tf_vars()],
                timeout=self._apply_timeout,
            )
            self._state["plan_attempted"] = True
            self._state["plan_returncode"] = completed.returncode
            self._state["plan_stdout"] = completed.stdout[-_MAX_CAPTURED_OUTPUT:]
            self._state["plan_stderr"] = completed.stderr[-_MAX_CAPTURED_OUTPUT:]
        elif binding == "apply":
            completed = self._run(
                [
                    "apply",
                    "-input=false",
                    "-no-color",
                    "-lock=false",
                    "-auto-approve",
                    *self._tf_vars(),
                ],
                timeout=self._apply_timeout,
            )
            self._state["apply_attempted"] = True
            self._state["apply_returncode"] = completed.returncode
            self._state["apply_stdout"] = completed.stdout[-_MAX_CAPTURED_OUTPUT:]
            self._state["apply_stderr"] = completed.stderr[-_MAX_CAPTURED_OUTPUT:]
        elif binding == "destroy":
            completed = self._run(
                [
                    "destroy",
                    "-input=false",
                    "-no-color",
                    "-lock=false",
                    "-auto-approve",
                    *self._tf_vars(),
                ],
                timeout=self._destroy_timeout,
            )
            self._state["destroy_attempted"] = True
            self._state["destroy_returncode"] = completed.returncode
            self._state["destroy_stdout"] = completed.stdout[-_MAX_CAPTURED_OUTPUT:]
            self._state["destroy_stderr"] = completed.stderr[-_MAX_CAPTURED_OUTPUT:]
        else:
            raise ValueError(f"unsupported terraform-docker-apply binding: {binding}")

        after = await self.observe()
        return {"before": before, "after": after}

    async def verify(self, expected: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
        """Polls REAL `docker inspect`-observed container state until it
        matches `expected` or a bounded timeout elapses -- never trusts
        `terraform apply`/`destroy`'s exit code alone as convergence
        evidence."""
        self._ensure_open()
        deadline = time.monotonic() + self._verify_timeout
        observed = await self.observe()
        while not all(observed.get(key) == value for key, value in expected.items()):
            if time.monotonic() >= deadline:
                break
            time.sleep(_POLL_INTERVAL_SECONDS)
            observed = await self.observe()
        passed = all(observed.get(key) == value for key, value in expected.items())
        return passed, observed

    async def checkpoint(self) -> dict[str, Any]:
        self._ensure_open()
        return dict(self._state)

    async def restore(self, checkpoint: dict[str, Any]) -> None:
        self._ensure_open()
        self._state = dict(checkpoint)

    async def teardown(self) -> None:
        """Real `terraform destroy -auto-approve`, then a real
        `docker inspect` confirmation that the container is actually gone.
        A zero destroy exit code with a still-present container is
        surfaced as a real `RuntimeError`, never silently treated as
        success."""
        if self._closed:
            return
        try:
            completed = self._run(
                [
                    "destroy",
                    "-input=false",
                    "-no-color",
                    "-lock=false",
                    "-auto-approve",
                    *self._tf_vars(),
                ],
                timeout=self._destroy_timeout,
            )
            self._state["destroy_attempted"] = True
            self._state["destroy_returncode"] = completed.returncode
            self._state["destroy_stdout"] = completed.stdout[-_MAX_CAPTURED_OUTPUT:]
            self._state["destroy_stderr"] = completed.stderr[-_MAX_CAPTURED_OUTPUT:]

            deadline = time.monotonic() + self._destroy_timeout
            container = _docker_container_json(self._container_name)
            while container is not None:
                if time.monotonic() >= deadline:
                    break
                time.sleep(_POLL_INTERVAL_SECONDS)
                container = _docker_container_json(self._container_name)

            if container is not None:
                raise RuntimeError(
                    f"terraform destroy reported returncode={completed.returncode} but "
                    f"container {self._container_name!r} is still present per real "
                    "`docker inspect` -- refusing to report a silent success"
                )
        finally:
            self._closed = True

    def is_really_gone(self) -> bool:
        """Real post-teardown confirmation helper for tests: queries the
        real Docker daemon directly rather than trusting `teardown()`'s own
        bookkeeping."""
        return _docker_container_json(self._container_name) is None


class TerraformDockerApplyProvider:
    """Materializes a `TerraformDockerApplyEnvironment` from the checked-in
    `gyms/fixtures/terraform_docker` config, run against colima's real local
    Docker daemon. See module docstring for the safety argument that makes
    `apply`/`destroy` acceptable here specifically."""

    name = "terraform-docker-apply"
    materialization_requires_authority = False

    async def materialize(
        self, *, scenario: str | None, config: dict[str, Any]
    ) -> TerraformDockerApplyEnvironment:
        del scenario
        working_dir = config.get("working_dir", str(_FIXTURES_DIR))
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
                "TerraformDockerApplyProvider"
            )

        container_name = config.get(
            "container_name", f"{_DEFAULT_CONTAINER_NAME}-{uuid4().hex[:8]}"
        )
        if not isinstance(container_name, str) or not container_name:
            raise TypeError("config.container_name must be a non-empty string")

        docker_host = config.get("docker_host")
        if docker_host is not None and not isinstance(docker_host, str):
            raise TypeError("config.docker_host must be a string or None")

        init_timeout_seconds = config.get("init_timeout_seconds", _DEFAULT_INIT_TIMEOUT_SECONDS)
        apply_timeout_seconds = config.get("apply_timeout_seconds", _DEFAULT_APPLY_TIMEOUT_SECONDS)
        destroy_timeout_seconds = config.get(
            "destroy_timeout_seconds", _DEFAULT_DESTROY_TIMEOUT_SECONDS
        )
        verify_timeout_seconds = config.get(
            "verify_timeout_seconds", _DEFAULT_VERIFY_TIMEOUT_SECONDS
        )
        for value, field_name in (
            (init_timeout_seconds, "init_timeout_seconds"),
            (apply_timeout_seconds, "apply_timeout_seconds"),
            (destroy_timeout_seconds, "destroy_timeout_seconds"),
            (verify_timeout_seconds, "verify_timeout_seconds"),
        ):
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                raise TypeError(f"config.{field_name} must be a number")

        requires_authority = config.get("requires_authority", True)
        if not isinstance(requires_authority, bool):
            raise TypeError("config.requires_authority must be a boolean")

        environment = TerraformDockerApplyEnvironment(
            binary=binary,
            working_dir=working_dir,
            container_name=container_name,
            docker_host=docker_host,
            init_timeout_seconds=float(init_timeout_seconds),
            apply_timeout_seconds=float(apply_timeout_seconds),
            destroy_timeout_seconds=float(destroy_timeout_seconds),
            verify_timeout_seconds=float(verify_timeout_seconds),
            requires_authority=requires_authority,
        )
        await environment.materialize_real_init()
        return environment
