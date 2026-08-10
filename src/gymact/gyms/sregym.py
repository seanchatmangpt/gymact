"""Real GymAct `Environment`/`EnvironmentProvider` backed by a real, exact-pinned
`sregym` checkout's real `main.py` subprocess and its real MCP/HTTP surface.

Unlike `vendor_benchmarks.py`'s `VendorBenchmarkProvider` (strictly one-shot
subprocess-per-call: `asyncio.create_subprocess_exec` -> `communicate()` ->
discarded), SREGym needs a PERSISTENT session across a whole multi-step trial
(repeated `kubectl` calls through its MCP surface, then a final diagnosis/
mitigation submission). `SregymEnvironment.__init__` therefore launches
`main.py` once as a long-lived subprocess and keeps a real `fastmcp.Client`
connection open against its `kubectl-mcp` server across every `actuate()`
call, matching `mcp_client_session.py`'s "open once, reuse" session pattern
rather than `vendor_benchmarks.py`'s "one subprocess per call" pattern.

Admission reuses `vendor_benchmarks.py`'s existing exact-pin machinery
(`audit_vendor`/`_audit_spec`/`VendorSpec`/`VENDOR_REVISIONS["sregym"]`)
rather than re-implementing pin-checking here.

Real argv/env shape: this module builds the `autofde_lab_planner` invocation
the same way `~/autofde-lab/src/autofde_lab/sota/materialize_sregym.py`'s
`materialize_sregym_autofde_lab_planner_invocation()` does (read at design
time, not imported -- this repo must not depend on `autofde-lab`):
`[".venv/bin/python", "main.py", "--agent", "autofde_lab_planner", "--model",
<judge_model_id>, "--problem", <problem_id>, "--agent-timeout",
<wall_clock_timeout_s>]`, with `AGENT_API_BASE`/`AGENT_API_KEY` env vars when
a judge API base/key placeholder is configured.

SREGym's real MCP/HTTP surface (per the sibling repo's own cited
investigation): a `kubectl-mcp` server at `MCP_SERVER_PORT` (default 9954),
endpoint `/kubectl/sse`, exposing tool `exec_kubectl_cmd_safely`; and a
conductor HTTP API at `API_PORT` (default 8000) exposing `/status` (used
here for `observe()`/`verify()` polling) and `/submit_mcp/sse` (an MCP
surface for `submit_diagnosis`/`submit_mitigation`, addressed with a second
real `fastmcp.Client`).
"""

from __future__ import annotations

import asyncio
import os
import subprocess
import time
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx
from fastmcp import Client

from gymact.gyms.vendor_benchmarks import VENDOR_SPECS, VendorAdmissionError, _audit_spec
from gymact.models import Capability, Consequence

_SPEC = VENDOR_SPECS["sregym"]

_DEFAULT_MCP_SERVER_PORT = 9954
_DEFAULT_API_PORT = 8000
_KUBECTL_TOOL_NAME = "exec_kubectl_cmd_safely"
_DEFAULT_STARTUP_TIMEOUT_SECONDS = 120.0
_DEFAULT_VERIFY_TIMEOUT_SECONDS = 120.0
_DEFAULT_TEARDOWN_TIMEOUT_SECONDS = 30.0
_POLL_INTERVAL_SECONDS = 1.0

SREGYM_CAPABILITIES = (
    Capability(
        iri="urn:gymact:sregym:capability:observe_cluster_state",
        title="Read SREGym's real conductor /status endpoint",
        consequence=Consequence.READ,
        binding="observe_cluster_state",
    ),
    Capability(
        iri="urn:gymact:sregym:capability:run_kubectl",
        title="Execute a real kubectl command through sregym's real kubectl-mcp server",
        consequence=Consequence.DO,
        binding="run_kubectl",
    ),
    Capability(
        iri="urn:gymact:sregym:capability:submit_diagnosis",
        title="Submit a real diagnosis to sregym's real conductor via its submit MCP surface",
        consequence=Consequence.DO,
        binding="submit_diagnosis",
    ),
    Capability(
        iri="urn:gymact:sregym:capability:submit_mitigation",
        title="Submit a real mitigation to sregym's real conductor via its submit MCP surface",
        consequence=Consequence.DO,
        binding="submit_mitigation",
    ),
    Capability(
        iri="urn:gymact:sregym:capability:get_benchmark_status",
        title="Read sregym's real conductor /status endpoint (benchmark-stage view)",
        consequence=Consequence.READ,
        binding="get_benchmark_status",
    ),
)


def _build_argv(
    *,
    judge_model_id: str,
    problem_id: str,
    wall_clock_timeout_s: int,
) -> list[str]:
    """Real argv shape, matching
    `materialize_sregym_autofde_lab_planner_invocation()` in the sibling
    autofde-lab repo (read, not imported -- this module has no dependency on
    that package)."""
    return [
        ".venv/bin/python",
        "main.py",
        "--agent",
        "autofde_lab_planner",
        "--model",
        judge_model_id,
        "--problem",
        problem_id,
        "--agent-timeout",
        str(wall_clock_timeout_s),
    ]


def _build_env(
    *, judge_api_base: str | None, judge_api_key_placeholder: str | None
) -> dict[str, str]:
    env: dict[str, str] = {}
    if judge_api_base:
        env["AGENT_API_BASE"] = judge_api_base
    if judge_api_key_placeholder:
        env["AGENT_API_KEY"] = judge_api_key_placeholder
    return env


def _build_full_subprocess_env(
    *, base_env: dict[str, str], mcp_server_port: int, api_port: int, overrides: dict[str, str]
) -> dict[str, str]:
    """Real defect fixed forward this session: `subprocess.Popen(env=...)`
    REPLACES the child process's entire environment rather than merging with
    the parent's -- so `base_env` (the caller's real `os.environ`, in
    production) must be the base, or real shell credentials (GROQ_API_KEY,
    PATH, kubeconfig-adjacent vars) silently never reach `main.py` regardless
    of whether they are correctly set in the parent shell. Reproduced live:
    `main.py`'s own Groq preflight check failed with "Invalid API Key" even
    though `GROQ_API_KEY` was confirmed set and exported in the calling
    shell -- because it was never forwarded. Extracted as its own function,
    separate from `SregymEnvironment.__init__`'s real subprocess launch, so
    this merge behavior is directly unit-testable without a live cluster."""
    return {
        **base_env,
        "MCP_SERVER_PORT": str(mcp_server_port),
        "API_PORT": str(api_port),
        **overrides,
    }


class SregymEnvironment:
    """Wraps one real `sregym` `main.py` subprocess plus a persistent real
    `fastmcp.Client` session against its real `kubectl-mcp` server.

    `__init__` starts the subprocess and waits (bounded, polling) for the
    real conductor HTTP API to answer `/status` before opening the real MCP
    client sessions -- SREGym's own server startup is not instantaneous and
    there is no other real readiness signal to wait on.
    """

    def __init__(
        self,
        *,
        root: Path,
        argv: list[str],
        env: dict[str, str],
        mcp_server_port: int,
        api_port: int,
        startup_timeout_seconds: float,
        verify_timeout_seconds: float,
        teardown_timeout_seconds: float,
        requires_authority: bool = True,
    ) -> None:
        self.environment_id = f"urn:gymact:sregym:environment:{uuid4().hex}"
        self.requires_authority = requires_authority
        self._root = root
        self._mcp_server_port = mcp_server_port
        self._api_port = api_port
        self._api_base = f"http://127.0.0.1:{api_port}"
        self._kubectl_mcp_url = f"http://127.0.0.1:{mcp_server_port}/kubectl/sse"
        self._submit_mcp_url = f"http://127.0.0.1:{api_port}/submit_mcp/sse"
        self._verify_timeout = verify_timeout_seconds
        self._teardown_timeout = teardown_timeout_seconds
        self._closed = False
        self._kubectl_client: Client | None = None
        self._submit_client: Client | None = None

        full_env = _build_full_subprocess_env(
            base_env=dict(os.environ),
            mcp_server_port=mcp_server_port,
            api_port=api_port,
            overrides=env,
        )
        # Real subprocess: sregym's own main.py, launched against its own
        # real vendored checkout root, exactly as vendor_benchmarks.py's
        # run_native() launches native vendor commands -- but kept alive
        # rather than communicate()-and-discard, since this trial needs a
        # persistent session across many calls.
        self._process = subprocess.Popen(
            argv,
            cwd=root,
            env=full_env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        deadline = time.monotonic() + startup_timeout_seconds
        last_error: Exception | None = None
        ready = False
        while time.monotonic() < deadline:
            if self._process.poll() is not None:
                stdout, stderr = self._process.communicate()
                raise RuntimeError(
                    f"sregym main.py exited during startup (returncode="
                    f"{self._process.returncode}): stderr={stderr[-4000:]!r}"
                )
            try:
                response = httpx.get(f"{self._api_base}/status", timeout=2.0)
                if response.status_code < 500:
                    ready = True
                    break
            except httpx.HTTPError as exc:
                last_error = exc
            time.sleep(_POLL_INTERVAL_SECONDS)
        if not ready:
            self._process.kill()
            self._process.wait(timeout=10.0)
            raise RuntimeError(
                f"sregym conductor API at {self._api_base} did not become ready within "
                f"{startup_timeout_seconds}s: last_error={last_error!r}"
            )

    async def _ensure_clients_open(self) -> None:
        if self._kubectl_client is None:
            self._kubectl_client = Client(self._kubectl_mcp_url)
            await self._kubectl_client.__aenter__()
        if self._submit_client is None:
            self._submit_client = Client(self._submit_mcp_url)
            await self._submit_client.__aenter__()

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError("environment is torn down")

    def capabilities(self) -> tuple[Capability, ...]:
        self._ensure_open()
        return SREGYM_CAPABILITIES

    def _status(self) -> dict[str, Any]:
        response = httpx.get(f"{self._api_base}/status", timeout=10.0)
        response.raise_for_status()
        return response.json()

    async def observe(self) -> dict[str, Any]:
        self._ensure_open()
        return self._status()

    async def actuate(self, capability: Capability, payload: dict[str, Any]) -> dict[str, Any]:
        self._ensure_open()
        await self._ensure_clients_open()
        binding = capability.binding
        before = self._status()
        if binding == "run_kubectl":
            command = payload.get("command")
            if not isinstance(command, str) or not command:
                raise TypeError("payload.command must be a non-empty string")
            assert self._kubectl_client is not None
            result = await self._kubectl_client.call_tool(
                _KUBECTL_TOOL_NAME, {"command": command}
            )
            after = self._status()
            return {
                "before": before,
                "after": after,
                "result_text": [block.model_dump(mode="json") for block in result.content],
            }
        if binding in ("submit_diagnosis", "submit_mitigation"):
            tool_name = binding
            args = dict(payload)
            assert self._submit_client is not None
            result = await self._submit_client.call_tool(tool_name, args)
            after = self._status()
            return {
                "before": before,
                "after": after,
                "result_text": [block.model_dump(mode="json") for block in result.content],
            }
        if binding in ("observe_cluster_state", "get_benchmark_status"):
            return {"before": before, "after": self._status()}
        raise ValueError(f"unsupported sregym binding: {binding}")

    async def verify(self, expected: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
        """Poll the real conductor `/status` endpoint until it matches
        `expected` (e.g. a real stage transition) or a bounded timeout
        elapses -- never trusts a single `/status` read as convergence."""
        self._ensure_open()
        deadline = time.monotonic() + self._verify_timeout
        observed = self._status()
        while not all(observed.get(key) == value for key, value in expected.items()):
            if time.monotonic() >= deadline:
                break
            time.sleep(_POLL_INTERVAL_SECONDS)
            observed = self._status()
        passed = all(observed.get(key) == value for key, value in expected.items())
        return passed, observed

    async def checkpoint(self) -> dict[str, Any]:
        """Real, but honestly minimal: the only thing this adapter can
        actually restore is its own process/session bookkeeping (root, argv
        shape, ports) -- it cannot roll back real cluster mutations already
        applied through kubectl, and does not pretend to."""
        self._ensure_open()
        return {
            "root": str(self._root),
            "mcp_server_port": self._mcp_server_port,
            "api_port": self._api_port,
        }

    async def restore(self, checkpoint: dict[str, Any]) -> None:
        """Real no-op beyond identity confirmation: cluster state already
        mutated by real kubectl calls is not revertible by this adapter, so
        `restore()` only asserts the checkpoint still describes this same
        live session rather than silently pretending to roll back the
        world."""
        self._ensure_open()
        if checkpoint.get("root") != str(self._root):
            raise VendorAdmissionError(
                "REFUSED:CHECKPOINT_ROOT_MISMATCH",
                f"expected={self._root},observed={checkpoint.get('root')}",
            )

    async def teardown(self) -> None:
        if self._closed:
            return
        try:
            if self._kubectl_client is not None:
                await self._kubectl_client.__aexit__(None, None, None)
                self._kubectl_client = None
            if self._submit_client is not None:
                await self._submit_client.__aexit__(None, None, None)
                self._submit_client = None
            self._process.terminate()
            try:
                self._process.wait(timeout=self._teardown_timeout)
            except subprocess.TimeoutExpired:
                self._process.kill()
                self._process.wait(timeout=10.0)
        finally:
            self._closed = True

    def is_really_stopped(self) -> bool:
        """Real post-teardown confirmation helper for tests: queries the
        real subprocess's own exit status directly rather than trusting
        `teardown()`'s own bookkeeping."""
        return self._process.poll() is not None


class SregymVendorProvider:
    """GymAct `EnvironmentProvider` that materializes real `SregymEnvironment`
    instances against a real, exact-pinned `sregym` checkout.

    Admission reuses `vendor_benchmarks.py`'s existing exact-pin machinery
    (`_audit_spec`/`VendorSpec`/`VENDOR_REVISIONS["sregym"]`) rather than
    duplicating pin-checking logic here.
    """

    name = "sregym"
    materialization_requires_authority = True

    async def materialize(
        self, *, scenario: str | None, config: dict[str, Any]
    ) -> SregymEnvironment:
        from gymact.gyms.vendor_benchmarks import vendor_root

        root_value = config.get("root")
        if root_value is not None and not isinstance(root_value, str):
            raise TypeError("config.root must be a string path when supplied")
        root = Path(root_value).expanduser() if root_value else vendor_root("sregym")

        audit = _audit_spec(_SPEC, root)
        if audit.standing != "PARTIAL_ALIVE":
            raise VendorAdmissionError(audit.reason, str(audit.root))

        judge_model_id = config.get("judge_model_id", "openai/gemma-4-26b-a4b-it")
        if not isinstance(judge_model_id, str) or not judge_model_id:
            raise TypeError("config.judge_model_id must be a non-empty string")
        problem_id = config.get("problem_id", scenario or "misconfig_app_hotel_res")
        if not isinstance(problem_id, str) or not problem_id:
            raise TypeError("config.problem_id must be a non-empty string")
        wall_clock_timeout_s = config.get("wall_clock_timeout_s", 600)
        if isinstance(wall_clock_timeout_s, bool) or not isinstance(
            wall_clock_timeout_s, int
        ):
            raise TypeError("config.wall_clock_timeout_s must be an int")
        judge_api_base = config.get("judge_api_base")
        if judge_api_base is not None and not isinstance(judge_api_base, str):
            raise TypeError("config.judge_api_base must be a string or None")
        judge_api_key_placeholder = config.get("judge_api_key_placeholder")
        if judge_api_key_placeholder is not None and not isinstance(
            judge_api_key_placeholder, str
        ):
            raise TypeError("config.judge_api_key_placeholder must be a string or None")
        mcp_server_port = config.get("mcp_server_port", _DEFAULT_MCP_SERVER_PORT)
        if isinstance(mcp_server_port, bool) or not isinstance(mcp_server_port, int):
            raise TypeError("config.mcp_server_port must be an int")
        api_port = config.get("api_port", _DEFAULT_API_PORT)
        if isinstance(api_port, bool) or not isinstance(api_port, int):
            raise TypeError("config.api_port must be an int")
        startup_timeout_seconds = config.get(
            "startup_timeout_seconds", _DEFAULT_STARTUP_TIMEOUT_SECONDS
        )
        verify_timeout_seconds = config.get(
            "verify_timeout_seconds", _DEFAULT_VERIFY_TIMEOUT_SECONDS
        )
        teardown_timeout_seconds = config.get(
            "teardown_timeout_seconds", _DEFAULT_TEARDOWN_TIMEOUT_SECONDS
        )
        requires_authority = config.get("requires_authority", True)
        if not isinstance(requires_authority, bool):
            raise TypeError("config.requires_authority must be a boolean")

        argv = _build_argv(
            judge_model_id=judge_model_id,
            problem_id=problem_id,
            wall_clock_timeout_s=int(wall_clock_timeout_s),
        )
        env = _build_env(
            judge_api_base=judge_api_base,
            judge_api_key_placeholder=judge_api_key_placeholder,
        )

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None,
            lambda: SregymEnvironment(
                root=audit.root,
                argv=argv,
                env=env,
                mcp_server_port=int(mcp_server_port),
                api_port=int(api_port),
                startup_timeout_seconds=float(startup_timeout_seconds),
                verify_timeout_seconds=float(verify_timeout_seconds),
                teardown_timeout_seconds=float(teardown_timeout_seconds),
                requires_authority=requires_authority,
            ),
        )
