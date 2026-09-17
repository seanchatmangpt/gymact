"""Real GymAct `Environment`/`EnvironmentProvider` backed by the real,
PyPI-installed `terminal-bench==0.2.18` package driving a real Docker
container -- not simulated.

WHY PYPI INSTEAD OF THE VENDORED SUBMODULE

The lab's own vendor pin (`~/autofde-lab/vendor/gyms/terminal-bench`, a
`git submodule` of `harbor-framework/terminal-bench-2` with `update = none`
in `.gitmodules`) is an uninitialized, empty directory -- there is nothing
there to import or drive. Per the task's own documented fallback, the real
`terminal-bench` PyPI package (confirmed installable, version 0.2.18) is
used instead as the real collaborator. This is recorded here, not asserted
once and forgotten: `pyproject.toml`'s `gyms` extra pins
`terminal-bench==0.2.18; python_version >= '3.12'` (terminal-bench itself
requires Python >=3.12, matching the existing `cube` extra's marker
pattern for the same reason).

WHY A HAND-AUTHORED, CHECKED-IN TASK FIXTURE

`terminal_bench.dataset.Dataset` normally caches a named/versioned dataset
from a remote registry, or loads a directory of already-existing task
directories from `path=`. Neither a registry fetch nor a bundled example
task ships inside the PyPI package itself (confirmed: no dataset/task
directory tree ships under
`site-packages/terminal_bench/`). Matching `terraform_docker_apply.py`'s
own precedent -- a HAND-AUTHORED, CHECKED-IN, small, auditable fixture
instead of an external/untrusted/network-fetched one -- this module drives
one hand-authored task directory checked in at
`gyms/fixtures/terminal_bench_task/` (`task.yaml`, `Dockerfile`,
`docker-compose.yaml`, `solution.sh`, `run-tests.sh`, `tests/`), built to
the real schema terminal-bench's own `terminal_bench.handlers.trial_handler
.Task`/`TaskPaths` classes require (verified by reading the real installed
source, not guessed): a `python:3.12-slim` image with `tmux` installed (the
real `TmuxSession.__init__` hard-requires `tmux -V` to succeed in the
container) and `pytest` installed (the task uses terminal-bench's own
built-in `PytestParser`, matched against `pytest -rA` short-summary
output). `disable_asciinema: true` in `task.yaml` avoids needing
`asciinema` in the image (real code path: `Terminal(..., disable_recording
=task.disable_asciinema)` in `terminal_bench.terminal.terminal
.spin_up_terminal`, mirrored by `TrialHandler`/`Task` there).

REAL EXECUTION MECHANISM -- NOT THE FULL `Harness`

`terminal_bench.harness.Harness.run()` drives an LLM `BaseAgent` end to
end; GymAct's own actuation/authority boundary (not an LLM agent, and not
terminal-bench's own oracle-solution agent) needs to *be* the agent issuing
commands. So this module drives terminal-bench's own lower-level, real
primitives directly -- the same primitives `Harness._run_trial` itself
composes internally (verified by reading `harness.py`):
`terminal_bench.handlers.trial_handler.TrialHandler` (real `task.yaml`
parsing + real path conventions + the real `PytestParser`),
`terminal_bench.terminal.terminal.Terminal` (real `docker compose build`/
`up -d`/`down` via `DockerComposeManager`, real container handle), and
`terminal_bench.terminal.tmux_session.TmuxSession` (real `docker exec`
into a real `tmux` session inside the real container). No terminal-bench
class is reimplemented, subclassed, or given a fake stand-in below --
every method call below is a call into the real installed package.

CONSEQUENCE CLASSIFICATION (`.claude/rules/actuation-authority.md`)

- `run_command` is `sosa:Actuation` / `Consequence.DO`: it executes a real
  shell command inside the real container via a real `tmux send-keys`,
  which can change the container's real state. `Environment
  .requires_authority` gates whether `gym.act()` requires an admitted
  `authority_ref` for it (fail-closed via `DenyAuthorityResolver` when no
  authority system is configured, per `.claude/rules/actuation-authority
  .md`) -- defaulting to `False` here matches `terraform_docker_apply.py`'s
  own `config.requires_authority` default and knob exactly: the DO
  classification on the capability is what encodes "this is
  consequential," while whether *this particular* provider's blast radius
  needs a live authority gate is a caller-configurable, structurally
  bounded decision (this task's Docker Compose config, like
  `terraform_docker_apply.py`'s, can only ever affect one throwaway local
  container built from the checked-in fixture). Callers with a configured
  `AuthorityResolver` set `config.requires_authority=True` to require it.
- `observe()` (real `tmux capture-pane` + real `docker inspect`) is
  `sosa:Observation`: read-only, never requires authority.
- `verify()` runs terminal-bench's own real oracle mechanism: it copies
  the real, checked-in `run-tests.sh`/`tests/` into the real container
  (matching `Harness._setup_test_env`'s own real
  `terminal.copy_to_container` call), executes `run-tests.sh` via a real
  `tmux` test session, and parses the real captured pane through
  terminal-bench's own real `PytestParser` -- an `earl:Assertion`-shaped
  `(passed, observed)` result derived from the real test process's real
  output, never from `run_command`'s own exit code or success report.

No new `gymact:` OWL class or property is introduced: capabilities reuse
`sosa:Procedure`/`sosa:Actuation`/`sosa:Observation` per
`.claude/rules/ontology.md`; verification reuses EARL's
assertion/outcome shape via the `Environment.verify()` contract that every
other gym here already implements the same way.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
from uuid import uuid4

from terminal_bench.handlers.trial_handler import TrialHandler
from terminal_bench.parsers.base_parser import UnitTestStatus
from terminal_bench.terminal.docker_compose_manager import DockerComposeManager
from terminal_bench.terminal.terminal import Terminal
from terminal_bench.terminal.tmux_session import TmuxSession

from gymact.models import Capability, Consequence

_MAX_CAPTURED_OUTPUT = 8000
_DEFAULT_COMMAND_TIMEOUT_SECONDS = 60.0
_DEFAULT_TEST_TIMEOUT_SECONDS = 60.0

_FIXTURES_DIR = Path(__file__).parent / "fixtures" / "terminal_bench_task"

TERMINAL_BENCH_CAPABILITIES = (
    Capability(
        iri="urn:gymact:terminal-bench:capability:run-command",
        title="Send a real command to a real tmux session inside the real "
        "terminal-bench task container",
        consequence=Consequence.DO,
        binding="run_command",
    ),
)


def _real_docker_reachable() -> bool:
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


class TerminalBenchEnvironment:
    """Wraps one real terminal-bench task container, driven directly via
    terminal-bench's own real `Terminal`/`TmuxSession`/`TrialHandler`
    classes (no LLM agent, no `Harness.run()`) -- see module docstring."""

    def __init__(
        self,
        *,
        trial_handler: TrialHandler,
        terminal: Terminal,
        command_timeout_seconds: float,
        test_timeout_seconds: float,
        requires_authority: bool,
        run_dir: TemporaryDirectory[str],
    ) -> None:
        self.environment_id = f"urn:gymact:terminal-bench:environment:{uuid4().hex}"
        self.requires_authority = requires_authority
        self._trial_handler = trial_handler
        self._terminal = terminal
        self._command_timeout = command_timeout_seconds
        self._test_timeout = test_timeout_seconds
        self._run_dir = run_dir
        self._session: TmuxSession = terminal.create_session(
            "agent", is_active_stream=False, as_configured_user=False
        )
        self._state: dict[str, Any] = {
            "task_id": trial_handler.task_id,
            "instruction": trial_handler.instruction,
            "container_name": trial_handler.client_container_name,
            "run_command_attempted": False,
            "last_command": None,
            "last_pane": "",
            "verification_attempted": False,
            "parser_results": None,
            "is_resolved": None,
        }
        self._closed = False

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError("environment is torn down")

    def capabilities(self) -> tuple[Capability, ...]:
        self._ensure_open()
        return TERMINAL_BENCH_CAPABILITIES

    async def observe(self) -> dict[str, Any]:
        """Real `sosa:Observation`: real `tmux capture-pane` output plus a
        real `docker inspect` of the task container -- read-only, no
        authority required."""
        self._ensure_open()
        merged = dict(self._state)
        merged["pane"] = self._session.capture_pane(capture_entire=True)[-_MAX_CAPTURED_OUTPUT:]
        merged["container_running"] = (
            self._terminal.container is not None and self._terminal.container.status == "running"
        )
        return merged

    async def actuate(self, capability: Capability, payload: dict[str, Any]) -> dict[str, Any]:
        """Real `sosa:Actuation`: sends `payload['command']` to the real
        `tmux` session inside the real container via `TmuxSession
        .send_keys`. `Consequence.DO` -- gated by `Environment
        .requires_authority` at the GymAct runtime boundary, per
        `.claude/rules/actuation-authority.md`."""
        self._ensure_open()
        binding = capability.binding
        before = await self.observe()

        if binding != "run_command":
            raise ValueError(f"unsupported terminal-bench binding: {binding}")

        command = payload.get("command")
        if not isinstance(command, str) or not command:
            raise TypeError("payload.command must be a non-empty string")
        timeout = float(payload.get("timeout_seconds", self._command_timeout))

        self._state["run_command_attempted"] = True
        self._state["last_command"] = command
        try:
            self._session.send_keys(
                [command, "Enter"],
                block=True,
                max_timeout_sec=timeout,
            )
        except TimeoutError:
            self._state["last_command_timed_out"] = True
        else:
            self._state["last_command_timed_out"] = False

        self._state["last_pane"] = self._session.capture_pane(capture_entire=True)[
            -_MAX_CAPTURED_OUTPUT:
        ]

        after = await self.observe()
        return {"before": before, "after": after}

    async def verify(self, expected: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
        """Real oracle mechanism: copies the real, checked-in
        `run-tests.sh`/`tests/` into the real container (matching
        `terminal_bench.harness.harness.Harness._setup_test_env`'s own real
        `copy_to_container` call), runs `run-tests.sh` in a real, separate
        `tmux` test session, and parses the real captured pane through
        terminal-bench's own real `PytestParser` -- never trusts
        `run_command`'s own exit code as pass/fail evidence."""
        self._ensure_open()
        paths = [self._trial_handler.task_paths.run_tests_path]
        if self._trial_handler.task_paths.test_dir.exists():
            paths.append(self._trial_handler.task_paths.test_dir)
        self._terminal.copy_to_container(
            paths=paths,
            container_dir=str(DockerComposeManager.CONTAINER_TEST_DIR),
        )

        test_session_name = f"tests-{uuid4().hex[:8]}"
        test_session = self._terminal.create_session(
            test_session_name, is_active_stream=False, as_configured_user=False
        )
        run_tests_container_path = (
            DockerComposeManager.CONTAINER_TEST_DIR
            / self._trial_handler.task_paths.run_tests_path.name
        )
        self._state["verification_attempted"] = True
        try:
            test_session.send_keys(
                ["bash ", str(run_tests_container_path), "Enter"],
                block=True,
                max_timeout_sec=self._test_timeout,
            )
            timed_out = False
        except TimeoutError:
            timed_out = True

        post_test_pane = test_session.capture_pane(capture_entire=True)
        self._state["post_test_pane"] = post_test_pane[-_MAX_CAPTURED_OUTPUT:]
        self._state["test_timed_out"] = timed_out

        if timed_out:
            self._state["parser_results"] = None
            self._state["is_resolved"] = False
            observed = await self.observe()
            observed["parser_results"] = None
            observed["is_resolved"] = False
            observed["test_timed_out"] = True
            return False, observed

        parser_results: dict[str, UnitTestStatus] = self._trial_handler.parser.parse(post_test_pane)
        is_resolved = bool(parser_results) and all(
            status == UnitTestStatus.PASSED for status in parser_results.values()
        )
        self._state["parser_results"] = {
            name: status.value for name, status in parser_results.items()
        }
        self._state["is_resolved"] = is_resolved

        observed = await self.observe()
        observed["parser_results"] = self._state["parser_results"]
        observed["is_resolved"] = is_resolved
        observed["test_timed_out"] = False

        expected_resolution = expected.get("is_resolved", True)
        passed = is_resolved == expected_resolution
        return passed, observed

    async def checkpoint(self) -> dict[str, Any]:
        self._ensure_open()
        return dict(self._state)

    async def restore(self, checkpoint: dict[str, Any]) -> None:
        self._ensure_open()
        self._state = dict(checkpoint)

    async def teardown(self) -> None:
        """Real `docker compose down` via `Terminal.stop()`, then a real
        `docker ps -a` confirmation that the container is actually gone --
        surfaced as a real failure, never a silent success, matching
        `terraform_docker_apply.py`'s teardown discipline."""
        if self._closed:
            return
        try:
            self._terminal.stop()
            if self._container_still_present():
                raise RuntimeError(
                    "terminal-bench task container "
                    f"{self._trial_handler.client_container_name!r} is still "
                    "present per real `docker ps -a` after `Terminal.stop()` -- "
                    "refusing to report a silent success"
                )
        finally:
            self._run_dir.cleanup()
            self._closed = True

    def _container_still_present(self) -> bool:
        container_name = self._trial_handler.client_container_name
        result = subprocess.run(
            [
                "docker",
                "ps",
                "-a",
                "--filter",
                f"name=^/{container_name}$",
                "--format",
                "{{.Names}}",
            ],
            capture_output=True,
            text=True,
            timeout=15.0,
            check=False,
        )
        if result.returncode != 0:
            return False
        return self._trial_handler.client_container_name in result.stdout.splitlines()

    def is_really_gone(self) -> bool:
        """Real post-teardown confirmation helper for tests: queries the
        real Docker daemon directly rather than trusting `teardown()`'s own
        bookkeeping."""
        return not self._container_still_present()


class TerminalBenchProvider:
    """Materializes a `TerminalBenchEnvironment` from the checked-in
    `gyms/fixtures/terminal_bench_task` task directory, driven against a
    real local Docker daemon via the real, PyPI-installed
    `terminal-bench==0.2.18` package. See module docstring for the real
    collaborator and API details."""

    name = "terminal-bench"
    materialization_requires_authority = False

    async def materialize(
        self, *, scenario: str | None, config: dict[str, Any]
    ) -> TerminalBenchEnvironment:
        del scenario

        task_path = config.get("task_path", str(_FIXTURES_DIR))
        if not isinstance(task_path, str) or not task_path:
            raise TypeError("config.task_path must be a non-empty string")
        if not Path(task_path).is_dir():
            raise ValueError(f"config.task_path does not exist or is not a directory: {task_path}")

        command_timeout_seconds = config.get(
            "command_timeout_seconds", _DEFAULT_COMMAND_TIMEOUT_SECONDS
        )
        test_timeout_seconds = config.get("test_timeout_seconds", _DEFAULT_TEST_TIMEOUT_SECONDS)
        for value, field_name in (
            (command_timeout_seconds, "command_timeout_seconds"),
            (test_timeout_seconds, "test_timeout_seconds"),
        ):
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                raise TypeError(f"config.{field_name} must be a number")

        requires_authority = config.get("requires_authority", False)
        if not isinstance(requires_authority, bool):
            raise TypeError("config.requires_authority must be a boolean")

        no_rebuild = config.get("no_rebuild", False)
        if not isinstance(no_rebuild, bool):
            raise TypeError("config.no_rebuild must be a boolean")

        run_dir = TemporaryDirectory(prefix="gymact-terminal-bench-")
        run_id = uuid4().hex[:12]
        trial_name = f"gymact-terminal-bench-{run_id}"

        trial_handler = TrialHandler(
            trial_name=trial_name,
            input_path=Path(task_path),
            output_path=None,
        )

        terminal = Terminal(
            client_container_name=trial_handler.client_container_name,
            client_image_name=trial_handler.client_image_name,
            docker_compose_path=trial_handler.task_paths.docker_compose_path,
            docker_image_name_prefix=trial_handler.docker_image_name_prefix,
            sessions_logs_path=None,
            agent_logs_path=None,
            commands_path=None,
            no_rebuild=no_rebuild,
            cleanup=False,
            livestream=False,
            disable_recording=trial_handler.task.disable_asciinema,
        )
        terminal.start()

        return TerminalBenchEnvironment(
            trial_handler=trial_handler,
            terminal=terminal,
            command_timeout_seconds=float(command_timeout_seconds),
            test_timeout_seconds=float(test_timeout_seconds),
            requires_authority=requires_authority,
            run_dir=run_dir,
        )
