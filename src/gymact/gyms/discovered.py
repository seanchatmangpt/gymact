"""One generic `Environment`/`EnvironmentProvider` for arbitrary discovered
gyms, driven by an LLM-produced recipe rather than a hand-written per-gym
adapter (unlike `cube_counter.py`/`cube_container_counter.py`, which are
hand-wired to one specific package each).

The recipe is deliberately narrow: a real subprocess command, a real working
directory, a real timeout, and expected success markers. This is the
`NATIVE_COMMAND` interaction family already named in this session's ontology
work (`docs/papers/generated/forwardbench/registry.json`) -- the largest
single family (34/80 subjects) and the one that generalizes across
heterogeneous CLI-invocable repositories without per-gym Python.

`actuate()` runs the real subprocess for real -- no simulated stdout, no
canned exit codes. A subject that fails to install/run reaches a real
`BLOCKED` standing with the real captured stderr as evidence; it is not
retried indefinitely or silently marked successful.
"""

from __future__ import annotations

import subprocess
from typing import Any
from uuid import uuid4

from gymact.models import Capability, Consequence

DISCOVERED_RUN_CAPABILITY = Capability(
    iri="urn:gymact:discovered:capability:run",
    title="Run the LLM-proposed command for this discovered subject",
    consequence=Consequence.DO,
    binding="run",
)

_MAX_CAPTURED_OUTPUT = 4000


class DiscoveredEnvironment:
    """Wraps one real subprocess command against one real, already-checked-out
    repository directory. No package is imported or pip-installed by this
    class itself -- the recipe's own command is responsible for that if
    needed (e.g. `pip install -e . && pytest -x -q`)."""

    def __init__(
        self,
        *,
        subject: str,
        command: list[str],
        cwd: str,
        timeout_seconds: float,
        success_markers: list[str],
        requires_authority: bool = False,
    ) -> None:
        if not command:
            raise ValueError("recipe command must be non-empty")
        self.environment_id = f"urn:gymact:discovered:environment:{uuid4().hex}"
        self.requires_authority = requires_authority
        self.subject = subject
        self._command = command
        self._cwd = cwd
        self._timeout = timeout_seconds
        self._success_markers = success_markers
        self._last_result: dict[str, Any] = {
            "subject": subject,
            "command": command,
            "attempted": False,
            "returncode": None,
            "stdout": "",
            "stderr": "",
            "timed_out": False,
            "solved": False,
        }
        self._closed = False

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError("environment is torn down")

    def capabilities(self) -> tuple[Capability, ...]:
        self._ensure_open()
        return (DISCOVERED_RUN_CAPABILITY,)

    async def observe(self) -> dict[str, Any]:
        self._ensure_open()
        return dict(self._last_result)

    async def actuate(self, capability: Capability, payload: dict[str, Any]) -> dict[str, Any]:
        del payload
        self._ensure_open()
        if capability.binding != "run":
            raise ValueError(f"unsupported discovered binding: {capability.binding}")

        before = dict(self._last_result)
        try:
            completed = subprocess.run(
                self._command,
                cwd=self._cwd,
                capture_output=True,
                text=True,
                timeout=self._timeout,
                check=False,
            )
            stdout = completed.stdout[-_MAX_CAPTURED_OUTPUT:]
            stderr = completed.stderr[-_MAX_CAPTURED_OUTPUT:]
            solved = completed.returncode == 0 and all(
                marker in stdout for marker in self._success_markers
            )
            self._last_result = {
                "subject": self.subject,
                "command": self._command,
                "attempted": True,
                "returncode": completed.returncode,
                "stdout": stdout,
                "stderr": stderr,
                "timed_out": False,
                "solved": solved,
            }
        except subprocess.TimeoutExpired as exc:
            self._last_result = {
                "subject": self.subject,
                "command": self._command,
                "attempted": True,
                "returncode": None,
                "stdout": (exc.stdout or "")[-_MAX_CAPTURED_OUTPUT:]
                if isinstance(exc.stdout, str)
                else "",
                "stderr": (exc.stderr or "")[-_MAX_CAPTURED_OUTPUT:]
                if isinstance(exc.stderr, str)
                else "",
                "timed_out": True,
                "solved": False,
            }
        except OSError as exc:
            self._last_result = {
                "subject": self.subject,
                "command": self._command,
                "attempted": True,
                "returncode": None,
                "stdout": "",
                "stderr": str(exc),
                "timed_out": False,
                "solved": False,
            }

        after = dict(self._last_result)
        return {"before": before, "after": after}

    async def verify(self, expected: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
        self._ensure_open()
        observed = dict(self._last_result)
        passed = all(observed.get(key) == value for key, value in expected.items())
        return passed, observed

    async def checkpoint(self) -> dict[str, Any]:
        self._ensure_open()
        return dict(self._last_result)

    async def restore(self, checkpoint: dict[str, Any]) -> None:
        self._ensure_open()
        self._last_result = dict(checkpoint)

    async def teardown(self) -> None:
        self._closed = True


class GenericDiscoveredProvider:
    """One provider, not 80: materializes a `DiscoveredEnvironment` from an
    LLM-produced recipe carried in `config`, not from per-gym Python code."""

    name = "discovered"
    materialization_requires_authority = False

    async def materialize(
        self, *, scenario: str | None, config: dict[str, Any]
    ) -> DiscoveredEnvironment:
        del scenario
        subject = config.get("subject")
        command = config.get("command")
        cwd = config.get("cwd")
        if not isinstance(subject, str) or not subject:
            raise TypeError("config.subject must be a non-empty string")
        if not isinstance(command, list) or not all(isinstance(c, str) for c in command):
            raise TypeError("config.command must be a list of strings")
        if not isinstance(cwd, str) or not cwd:
            raise TypeError("config.cwd must be a non-empty string")
        timeout_seconds = config.get("timeout_seconds", 60.0)
        if not isinstance(timeout_seconds, (int, float)) or isinstance(timeout_seconds, bool):
            raise TypeError("config.timeout_seconds must be a number")
        success_markers = config.get("success_markers", [])
        if not isinstance(success_markers, list) or not all(
            isinstance(m, str) for m in success_markers
        ):
            raise TypeError("config.success_markers must be a list of strings")
        requires_authority = config.get("requires_authority", False)
        if not isinstance(requires_authority, bool):
            raise TypeError("config.requires_authority must be a boolean")
        return DiscoveredEnvironment(
            subject=subject,
            command=command,
            cwd=cwd,
            timeout_seconds=float(timeout_seconds),
            success_markers=success_markers,
            requires_authority=requires_authority,
        )
