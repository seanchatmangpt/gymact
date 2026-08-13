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

Real argv/env shape: this module builds the sregym client invocation the same
way `~/autofde-lab/src/autofde_lab/sota/materialize_sregym.py`'s
`materialize_sregym_autofde_lab_planner_invocation()` does (read at design
time, not imported -- this repo must not depend on `autofde-lab`):
`[".venv/bin/python", "main.py", "--agent", <agent_name>, "--model",
<judge_model_id>, "--problem", <problem_id>, "--agent-timeout",
<wall_clock_timeout_s>]`, with `AGENT_API_BASE`/`AGENT_API_KEY` env vars when
a judge API base/key placeholder is configured. `agent_name` defaults to
`"debug"` (config key `config.agent_name`), a pre-existing `agents.yaml`
entry that pauses and keeps the conductor alive for external driving --
see `_build_argv`'s own docstring below for the full rationale.

SREGym's real MCP/HTTP surface (confirmed directly against the real vendored
`mcp_server/sregym_mcp_server.py`, not guessed): one real MCP server process
at `MCP_SERVER_PORT` (default 9954) mounts FIVE real SSE routes --
`/kubectl` (tool `exec_kubectl_cmd_safely`), `/jaeger` (tools `get_services`,
`get_operations`, `get_traces`, `get_dependency_graph`), `/loki` (tools
`get_logs`, `get_labels`, `get_label_values`), `/prometheus` (tools
`get_metrics`, `get_alerts`), and `/submit` (tool `submit`). This module
wires real `fastmcp.Client` connections to `kubectl`/`jaeger`/`loki`/
`prometheus` on that one port; `submit` is addressed separately via the
conductor HTTP API's own `/submit_mcp/sse` at `API_PORT` (default 8000),
which also exposes `/status` (used here for `observe()`/`verify()`
polling) -- this is a real, pre-existing routing difference between the
generic MCP server's own `/submit` and the conductor's `/submit_mcp/sse`,
not a naming inconsistency to "fix."
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import signal
import socket
import subprocess
import tempfile
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx
from fastmcp import Client

from gymact.gyms.vendor_benchmarks import VendorAdmissionError, VendorSpec, _audit_spec
from gymact.models import Capability, Consequence
from gymact.polling import poll_until

# Not sourced from `vendor_benchmarks.VENDOR_REVISIONS`: that dict is an exact,
# lock-derived corpus (`tests/test_vendor_benchmarks.py` pins its own length and
# `LOCK_SOURCE_SHA`) -- adding an entry by hand here would misrepresent this pin
# as lock-derived when it isn't. `_audit_spec`/`VendorSpec` are still reused
# (the real, shared exact-pin admission machinery); only the spec's construction
# is local to this module.
_SPEC = VendorSpec(name="sregym", revision="ba07faf1a322f9b6d4a279643bb796aa2f36f64b")


def _default_root() -> Path:
    """Reproduces `vendor_benchmarks.vendor_root()`'s real layout
    (`<lab_root>/vendor/gyms/sregym`) without depending on that helper's
    `VENDOR_SPECS` lookup, which does not contain `"sregym"` (see `_SPEC`
    above)."""
    configured = os.environ.get("AUTOFDE_LAB")
    lab_root = Path(configured).expanduser() if configured else Path.home() / "autofde-lab"
    return lab_root / _SPEC.relative_root


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
        consequence=Consequence.DO,
        binding="observe_cluster_state",
    ),
    Capability(
        iri="urn:gymact:sregym:capability:run_kubectl",
        # `Capability` has no payload-schema field; naming the real required
        # payload key directly in the title is the same generic-discovery
        # stopgap already applied to MEMORY_CAPABILITIES (providers.py) --
        # found real and necessary via gymact.dspy_agent's grounding-guard
        # investigation this session: this value is a composed command
        # string (not a bare reference), a real, separate gap tracked by the
        # gymact-capability-schema-pack plan.
        title=(
            "Execute a real kubectl command through sregym's real kubectl-mcp server. "
            'Payload: {"command": <str, a full kubectl command line>}.'
        ),
        consequence=Consequence.DO,
        binding="run_kubectl",
    ),
    Capability(
        iri="urn:gymact:sregym:capability:submit_diagnosis",
        title=(
            "Submit a real diagnosis to sregym's real conductor via its submit MCP surface. "
            "Payload: any free-form JSON-serializable dict describing the diagnosis "
            "(no fixed required keys -- rendered as-is into the real submit answer)."
        ),
        consequence=Consequence.DO,
        binding="submit_diagnosis",
    ),
    Capability(
        iri="urn:gymact:sregym:capability:submit_mitigation",
        title=(
            "Submit a real mitigation to sregym's real conductor via its submit MCP surface. "
            "Payload: any free-form JSON-serializable dict describing the mitigation "
            "(no fixed required keys -- rendered as-is into the real submit answer)."
        ),
        consequence=Consequence.DO,
        binding="submit_mitigation",
    ),
    Capability(
        iri="urn:gymact:sregym:capability:get_benchmark_status",
        title="Read sregym's real conductor /status endpoint (benchmark-stage view)",
        consequence=Consequence.DO,
        binding="get_benchmark_status",
    ),
    # Real Jaeger/Loki/Prometheus MCP capabilities -- confirmed directly
    # against the real vendored `mcp_server/{jaeger,loki,prometheus}_
    # server.py` tool signatures, not guessed. Semantically these are pure
    # queries (no cluster mutation), but declared `Consequence.DO`, not
    # `READ` -- a real, live-confirmed defect this session found: gymact's
    # own kernel (`kernel.py`) mechanically refuses ANY `Consequence.READ`
    # capability routed through `gym.act()`
    # (`REFUSED:READ_CAPABILITY_IS_NOT_ACTUATION`), and `SregymEnvironment`
    # has no separate `observe()`-based invocation path for a named query
    # (`observe()` only ever returns the fixed `/status` stage marker) --
    # `gym.act()` is the ONLY real way these tools can actually execute,
    # so `DO` is the only classification that is actually true here,
    # matching the existing precedent already set by `run_kubectl` (also
    # semantically read-only for `get`/`describe` commands, also `DO`).
    # This same defect was real and already present, silently, on
    # `observe_cluster_state`/`get_benchmark_status` above -- both were
    # `READ` and both have been refused by every real `gym.act()` call
    # against them since before this session began; fixed alongside these.
    # `epistemic_process_kernel.run_episode` still picks all of these up
    # automatically (its `read_capabilities` list includes every real
    # non-`submit` `DO` capability, not only literal `READ` ones) -- no
    # kernel-side change was needed once this classification was fixed.
    Capability(
        iri="urn:gymact:sregym:capability:jaeger_get_services",
        title="Real Jaeger MCP get_services -- list real service names. Payload: {}.",
        consequence=Consequence.DO,
        binding="jaeger_get_services",
    ),
    Capability(
        iri="urn:gymact:sregym:capability:jaeger_get_operations",
        title=(
            'Real Jaeger MCP get_operations -- real operations for one service. Payload: '
            '{"service": <str>}.'
        ),
        consequence=Consequence.DO,
        binding="jaeger_get_operations",
    ),
    Capability(
        iri="urn:gymact:sregym:capability:jaeger_get_traces",
        title=(
            "Real Jaeger MCP get_traces -- real traces for one service in a real time "
            'window. Payload: {"service": <str>, "last_n_minutes": <int>}.'
        ),
        consequence=Consequence.DO,
        binding="jaeger_get_traces",
    ),
    Capability(
        iri="urn:gymact:sregym:capability:jaeger_get_dependency_graph",
        title=(
            "Real Jaeger MCP get_dependency_graph -- real service dependency graph. "
            'Payload: {"last_n_minutes": <int, optional, default 30>}.'
        ),
        consequence=Consequence.DO,
        binding="jaeger_get_dependency_graph",
    ),
    Capability(
        iri="urn:gymact:sregym:capability:loki_get_logs",
        title=(
            "Real Loki MCP get_logs -- real logs matching a real LogQL query. Payload: "
            '{"query": <str, LogQL>, "last_n_minutes": <int, optional, default 15>}.'
        ),
        consequence=Consequence.DO,
        binding="loki_get_logs",
    ),
    Capability(
        iri="urn:gymact:sregym:capability:loki_get_labels",
        title="Real Loki MCP get_labels -- real available label names. Payload: {}.",
        consequence=Consequence.DO,
        binding="loki_get_labels",
    ),
    Capability(
        iri="urn:gymact:sregym:capability:loki_get_label_values",
        title=(
            'Real Loki MCP get_label_values -- real values for one label. Payload: '
            '{"label": <str, e.g. "namespace"/"app"/"pod">}.'
        ),
        consequence=Consequence.DO,
        binding="loki_get_label_values",
    ),
    Capability(
        iri="urn:gymact:sregym:capability:prometheus_get_metrics",
        title=(
            "Real Prometheus MCP get_metrics -- real metric values for a real PromQL "
            'query. Payload: {"query": <str, PromQL>}.'
        ),
        consequence=Consequence.DO,
        binding="prometheus_get_metrics",
    ),
    Capability(
        iri="urn:gymact:sregym:capability:prometheus_get_alerts",
        title="Real Prometheus MCP get_alerts -- real currently-firing alerts. Payload: {}.",
        consequence=Consequence.DO,
        binding="prometheus_get_alerts",
    ),
)


def _build_argv(
    *,
    agent_name: str = "debug",
    judge_model_id: str,
    problem_id: str,
    wall_clock_timeout_s: int,
) -> list[str]:
    """Real argv shape, matching
    `materialize_sregym_autofde_lab_planner_invocation()` in the sibling
    autofde-lab repo (read, not imported -- this module has no dependency on
    that package).

    `agent_name` defaults to `"debug"` -- NOT `autofde_lab_dspy`, and NOT
    `--use-external-harness` either. Both were tried and empirically
    disproven live this session, in order:

    1. `autofde_lab_planner`: `vendor/gyms/sregym/clients/autofde_lab_planner/
       driver.py` does not exist on disk in the sibling autofde-lab checkout
       (`No module named clients.autofde_lab_planner.driver`).
    2. `autofde_lab_dspy`: the driver exists and runs, but `main.py` launches
       it, waits for it to run its OWN complete internal benchmark loop to
       conclusion, then tears the whole process down -- `SregymEnvironment`
       never gets a chance to drive anything externally; by the time it polls
       again the subprocess has already exited (confirmed live: `returncode=0`,
       full `"Benchmark complete!"` trace in stdout).
    3. `--use-external-harness`: deploys the fault, then exits the whole
       process immediately (`"Fault injected... exit for external harness"`
       followed immediately by `"Finished server process"`) -- also does not
       stay alive.
    4. `"debug"` (this default): a real, pre-existing `agents.yaml` entry
       (`kickoff_command: python -c "import signal; signal.pause()"`) that
       does nothing. Confirmed live: the conductor deploys the fault, launches
       `debug` (which just pauses), and the outer `while
       conductor.submission_stage != "done":` loop in `main.py` keeps the
       conductor's real HTTP API alive and responsive
       (`curl http://127.0.0.1:8000/status` returned real
       `{"stage":"diagnosis"}` while this was running) -- waiting for an
       EXTERNAL caller (this module's `actuate()`, via `submit_diagnosis`/
       `submit_mitigation`) to flip that stage. This is the real, working
       persistent-server pattern `SregymEnvironment` was designed for.

    `autofde_lab_planner`/`autofde_lab_dspy`/`--use-external-harness` remain
    reachable by passing `agent_name` explicitly for callers who want a
    self-contained one-shot benchmark run instead of external MCP-mediated
    control -- the point of this default is which mode matches THIS module's
    own `observe()`/`actuate()`/`verify()` design, not that the others are
    wrong for their own purpose."""
    return [
        ".venv/bin/python",
        "main.py",
        "--agent",
        agent_name,
        "--model",
        judge_model_id,
        "--problem",
        problem_id,
        "--agent-timeout",
        str(wall_clock_timeout_s),
    ]


_CLIENT_CONNECT_RETRIES = 10
_CLIENT_CONNECT_RETRY_DELAY_SECONDS = 3.0


async def _connect_with_retry(client_factory, *, label: str) -> Any:
    """Real, bounded retry around a real `fastmcp.Client.__aenter__()` call.

    Real gap found and fixed forward this session: `__init__`'s own
    readiness wait (`_tcp_port_reachable`, added earlier this session)
    proves a TCP listener exists, but a raw TCP accept succeeding does not
    prove the actual port-forward/MCP protocol handshake behind it is
    ready -- confirmed live: `_tcp_port_reachable` passed, `__init__`
    returned "ready", and the very next real `_ensure_clients_open()` call
    still failed with `RuntimeError: Client failed to connect: All
    connection attempts failed`. A bounded retry at the actual point of use
    is the correct fix, not a stronger pre-check (no pre-check can fully
    predict a later real handshake's success).

    Takes a `client_factory` (builds a FRESH `Client` per attempt), not a
    single pre-built client -- a real, second defect found immediately after
    the first retry fix landed: retrying `__aenter__()` on the SAME
    already-failed `Client` instance left it in a broken internal state
    (confirmed live: `RuntimeError: Client is not connected. Use the 'async
    with client:' context manager first.` on the very next real use, even
    though this function's own retry loop had reported success). A fresh
    `Client` object per attempt is the only real-connection-shaped fix here;
    reusing a once-failed async-context-manager instance is not a safe
    assumption to make about a third-party client.

    Budget widened this session (5 attempts/2s -> 10 attempts/3s, 10s -> 30s
    total) after a real live trial exhausted the original 5x2s budget with
    NO zombie port-forward present and a genuinely fast (~69s total)
    `__init__` -- real evidence the gap between a port-forward becoming
    TCP-acceptable and the pod-side MCP server actually completing a real
    handshake can exceed 10s under this session's real, accumulated cluster
    load. Every real per-attempt error is now collected (not just the
    final one) so a recurrence is diagnosable from the raised message alone,
    without a second manual repro."""
    attempt_errors: list[str] = []
    for attempt in range(1, _CLIENT_CONNECT_RETRIES + 1):
        client = client_factory()
        try:
            await client.__aenter__()
            return client
        except Exception as exc:  # noqa: BLE001 -- real connection failures come in several real exception types (RuntimeError, ConnectError, ...)
            attempt_errors.append(f"attempt {attempt}: {type(exc).__name__}: {exc}")
            if attempt < _CLIENT_CONNECT_RETRIES:
                await asyncio.sleep(_CLIENT_CONNECT_RETRY_DELAY_SECONDS)
    raise RuntimeError(
        f"real MCP client {label!r} failed to connect after "
        f"{_CLIENT_CONNECT_RETRIES} real attempts over "
        f"{_CLIENT_CONNECT_RETRIES * _CLIENT_CONNECT_RETRY_DELAY_SECONDS:.0f}s total: "
        + " | ".join(attempt_errors)
    )


@contextlib.asynccontextmanager
async def _open_client_with_retry(client_factory, *, label: str):
    """Real, connect-use-close-fresh-every-call client lifecycle.

    Real, architectural defect found and fixed forward this session,
    deeper than the two connection-layer fixes above: `SregymEnvironment`
    previously cached `_kubectl_client`/`_submit_client` as persistent
    instance state, opened once and reused across many `actuate()`/
    `verify()` calls -- explicitly built that way for efficiency (see this
    module's own top docstring). But the real caller
    (`autofde_lab.reasoning.gymact_diagnosis_driver`) runs each
    `action_bindings` closure inside its OWN fresh event loop
    (`ThreadPoolExecutor` + `asyncio.run()` per call, required because each
    closure runs inside `run_pipeline`'s synchronous callback, which may
    already be inside a running loop). A client's underlying async
    transport/tasks are bound to the event loop that created them; reusing
    a client across two different `asyncio.run()` invocations is not a
    race, it is a structural impossibility -- confirmed live, deterministic,
    100% reproduction rate past the first real client-using call:
    `RuntimeError: Client is not connected. Use the 'async with client:'
    context manager first.`

    Fixed: every real operation now opens its own fresh client (via the
    already-real `_connect_with_retry` bounded retry), uses it, and closes
    it -- entirely within the ONE event loop that is actually running this
    coroutine, never persisted on `self` across calls. This trades one real
    connect/disconnect round-trip per operation for correctness; matches
    `vendor_benchmarks.py`'s own one-shot-per-call precedent in this same
    package, which never had this problem for exactly this reason."""
    client = await _connect_with_retry(client_factory, label=label)
    try:
        yield client
    finally:
        with contextlib.suppress(Exception):
            await client.__aexit__(None, None, None)


def _tcp_port_reachable(host: str, port: int, *, timeout: float) -> bool:
    """Real, lightweight TCP-connect probe -- no HTTP/MCP protocol handshake
    needed, just proof something is actually listening on `port` before a
    real `fastmcp.Client` attempts its own full connection later. Real
    socket, real connect attempt, closed immediately; never a mock."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


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


def _render_submit_answer(binding: str, payload: dict[str, Any]) -> str:
    """Render a `submit_diagnosis`/`submit_mitigation` capability payload
    into the single real free-text answer the real sregym `submit` MCP tool
    actually accepts (see `SregymEnvironment.actuate()`'s own docstring for
    the full account of why this exists). Deterministic JSON rendering
    (`sort_keys=True`) so the same payload always renders the same text --
    real, testable, no cluster needed."""
    return json.dumps({"kind": binding, "payload": payload}, sort_keys=True)


class SregymEnvironment:
    """Wraps one real `sregym` `main.py` subprocess and opens a fresh real
    `fastmcp.Client` session per real `actuate()` call against its real
    `kubectl-mcp`/submit-MCP servers.

    `__init__` starts the subprocess and waits (bounded, polling) for both
    the real conductor HTTP API AND the kubectl-mcp port to become reachable
    before returning -- SREGym's own server startup is not instantaneous and
    there is no other real readiness signal to wait on.

    Real, architectural correction made this session: this class previously
    cached one persistent `Client` per (kubectl/submit) surface, opened once
    and reused across every `actuate()` call, for efficiency. That is
    incompatible with the real caller
    (`autofde_lab.reasoning.gymact_diagnosis_driver`), which runs each real
    binding inside its own fresh event loop -- a client's async
    transport/tasks are bound to the loop that created them, so reusing one
    across two different `asyncio.run()` invocations is a structural
    impossibility, not a race (confirmed live, deterministic, 100%
    reproduction past the first real client-using call). Each `actuate()`
    call now opens, uses, and closes its own client via
    `_open_client_with_retry`, entirely within whichever single event loop
    is actually running that one call -- see that function's own docstring
    for the full account."""

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
        self._jaeger_mcp_url = f"http://127.0.0.1:{mcp_server_port}/jaeger/sse"
        self._loki_mcp_url = f"http://127.0.0.1:{mcp_server_port}/loki/sse"
        self._prometheus_mcp_url = f"http://127.0.0.1:{mcp_server_port}/prometheus/sse"
        self._submit_mcp_url = f"http://127.0.0.1:{api_port}/submit_mcp/sse"
        self._verify_timeout = verify_timeout_seconds
        self._teardown_timeout = teardown_timeout_seconds
        self._closed = False

        # Real defect found and fixed forward this session: `stdout=PIPE,
        # stderr=PIPE` was never drained during normal operation (only
        # `communicate()`d on the startup-failure path) -- main.py's own
        # real conductor logs (including the real per-stage `[EVAL]
        # Diagnosis/Mitigation Succeed/Failed` grading lines) were silently
        # discarded, and a sufficiently chatty subprocess could deadlock on
        # a full OS pipe buffer never being read. Redirecting to a real,
        # readable log file on disk fixes both: nothing is lost, and
        # `read_log_tail()` lets a caller (or this class's own
        # startup-failure branch below) read the real subprocess output at
        # any time without needing `communicate()` (which requires PIPE and
        # only works once, at process exit).
        self._log_fh = tempfile.NamedTemporaryFile(  # noqa: SIM115 - kept open for the subprocess's lifetime
            mode="w+", suffix=".sregym.log", delete=False, encoding="utf-8"
        )
        self.log_path = Path(self._log_fh.name)

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
        # Real defect found and fixed forward this session (cycle 10): main.py
        # spawns its own child `kubectl port-forward svc/mcp-server ...`
        # process. Without `start_new_session=True` that grandchild is NOT in
        # the same process group as `self._process`, so `teardown()`'s
        # `self._process.terminate()`/`kill()` only ever signals the direct
        # child -- the port-forward survives as a real, live orphan, confirmed
        # repeatedly this session (found and killed 3 separate times across
        # cycle 9 alone, each time discovered via `ps aux` before relaunching
        # a trial). `start_new_session=True` puts the whole subprocess tree in
        # its own process group so `teardown()` can signal the group, not just
        # the one PID it holds a handle to.
        self._process = subprocess.Popen(
            argv,
            cwd=root,
            env=full_env,
            stdout=self._log_fh,
            stderr=subprocess.STDOUT,
            text=True,
            start_new_session=True,
        )

        last_error: Exception | None = None
        api_ready = False
        mcp_ready = False

        def _startup_check() -> bool:
            nonlocal api_ready, mcp_ready, last_error
            if self._process.poll() is not None:
                # Real defect fixed forward this session: main.py's own rich
                # logging writes diagnostic output to stdout, not stderr --
                # confirmed live, multiple times, when this error's stderr
                # was empty or just deprecation-warning noise while the real
                # cause (a Groq preflight failure, a port conflict, etc.) sat
                # in stdout the caller never saw. Both streams are now
                # merged into one real log file (`stderr=STDOUT`) so a real
                # failure is actually diagnosable from the raised message
                # alone, not a second manual repro.
                log_tail = self.read_log_tail()
                raise RuntimeError(
                    f"sregym main.py exited during startup (returncode="
                    f"{self._process.returncode}): log_tail={log_tail!r}"
                )
            if not api_ready:
                try:
                    response = httpx.get(f"{self._api_base}/status", timeout=2.0)
                    if response.status_code < 500:
                        api_ready = True
                except httpx.HTTPError as exc:
                    last_error = exc
            # Real defect found and fixed forward this session: this loop
            # previously only waited for the conductor API's /status to
            # respond, never for the SEPARATE kubectl-mcp server/port-forward
            # (confirmed live, in real logs, to become reachable on its own,
            # LATER timeline than /status: "Port forwarding established at
            # 9954" is logged after conductor readiness). A caller's first
            # real actuate() call could race that gap and fail with
            # `RuntimeError: Client failed to connect: All connection
            # attempts failed` -- reproduced live. Both signals are now
            # required before `ready`, not just the API's.
            if api_ready and not mcp_ready:
                mcp_ready = _tcp_port_reachable("127.0.0.1", mcp_server_port, timeout=1.0)
            return api_ready and mcp_ready

        try:
            poll_until(
                _startup_check,
                timeout_seconds=startup_timeout_seconds,
                interval_seconds=_POLL_INTERVAL_SECONDS,
            )
        except Exception:
            # Real defect found by an adversarial gap-hunt this session,
            # fixed forward: `poll_until` (per its own documented contract
            # in `polling.py`) propagates a raising `condition()` --
            # including `_startup_check`'s own `RuntimeError` for the
            # process-exited-during-startup case above -- immediately,
            # unwinding straight out of this `try` without ever reaching
            # the timeout branch below. That skipped cleanup entirely on
            # this specific path: `self._log_fh` stayed open (a real,
            # live-reproduced `ResourceWarning: unclosed file` this
            # session) and `_kill_process_group` was never called, so the
            # already-spawned subprocess (and its `kubectl port-forward`
            # grandchild -- the exact orphan class `_kill_process_group`'s
            # own docstring already documents fixing on the *timeout*
            # path) relied only on its own crash to die, not an explicit
            # kill. Same cleanup as the timeout branch, on every raising
            # startup-check failure, not just the timeout one.
            self._kill_process_group(10.0)
            self._log_fh.close()
            raise
        if not (api_ready and mcp_ready):
            # Real defect found and fixed forward this session: this used
            # to be a bare `self._process.kill()` -- only the direct
            # main.py PID, never the real Docker container/kubectl
            # port-forward children it had already spawned by the time of
            # a real startup timeout. See `_kill_process_group`'s own
            # docstring for the full, confirmed-live account (multiple
            # real orphaned `docker run --cpus=4.0 --memory=8g` containers
            # found accumulated on this machine, which then starved a
            # LATER materialize() attempt).
            self._kill_process_group(10.0)
            self._log_fh.close()
            raise RuntimeError(
                f"sregym did not become fully ready within {startup_timeout_seconds}s "
                f"(conductor API ready={api_ready}, kubectl-mcp port {mcp_server_port} "
                f"reachable={mcp_ready}): last_error={last_error!r}"
            )

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

    def _safe_status(self) -> dict[str, Any]:
        """Real defect found and fixed forward this session, via an actual
        live trial: `actuate()`'s own `before`/`after` bookkeeping calls
        `self._status()` directly -- a single, real, transient
        `httpx.ReadTimeout` there (confirmed live: `submit_diagnosis`'s
        `before = self._status()` call) crashed the WHOLE `actuate()` call,
        discarding a real, independent action (a real kubectl/submit MCP
        tool call) that may have succeeded or was about to run, purely
        because its surrounding diagnostic status snapshot failed. This is
        the exact same class of defect an earlier session already fixed for
        `verify()`'s own polling loop (a transient status-read failure must
        degrade to an honest `{}` non-answer, never crash the real, larger
        operation it's wrapped around) -- `actuate()`'s `before`/`after`
        snapshots never got that same resilience. Fixed here: any real
        exception from `_status()` degrades to a real, honest `{}` (an
        explicit non-answer, matching `verify()`'s own established
        contract), never propagates and aborts the real action underway."""
        try:
            return self._status()
        except Exception:
            return {}

    async def observe(self) -> dict[str, Any]:
        self._ensure_open()
        return self._status()

    def read_log_tail(self, n_chars: int = 4000) -> str:
        """Real, current tail of the real subprocess's merged stdout+stderr
        log file -- readable at any time (the file is real, on disk; no
        `communicate()`/process-exit requirement). Returns "" if the log
        file isn't available yet (e.g. this instance was constructed
        directly, bypassing `__init__`, as some tests do)."""
        log_path = getattr(self, "log_path", None)
        if log_path is None:
            return ""
        try:
            return log_path.read_text(encoding="utf-8", errors="replace")[-n_chars:]
        except OSError:
            return ""

    async def actuate(self, capability: Capability, payload: dict[str, Any]) -> dict[str, Any]:
        self._ensure_open()
        binding = capability.binding
        before = self._safe_status()
        if binding == "run_kubectl":
            command = payload.get("command")
            if not isinstance(command, str) or not command:
                raise TypeError("payload.command must be a non-empty string")
            # Real defect found and fixed forward this session: the real
            # exec_kubectl_cmd_safely MCP tool's schema requires the
            # argument named `cmd`, not `command` -- confirmed live
            # (`fastmcp.exceptions.ToolError`: "cmd Missing required
            # argument" / "command Unexpected keyword argument") and
            # cross-checked against every other real client in the
            # vendored sregym checkout (clients/demo, clients/stratus),
            # all of which already call it with `{"cmd": ...}`. This
            # module's own `payload["command"]` key name (this class's own
            # external API) is unaffected -- only the real MCP call's own
            # argument name changes to match the real tool.
            async with _open_client_with_retry(
                lambda: Client(self._kubectl_mcp_url), label="kubectl_client"
            ) as kubectl_client:
                result = await kubectl_client.call_tool(_KUBECTL_TOOL_NAME, {"cmd": command})
            after = self._safe_status()
            return {
                "before": before,
                "after": after,
                "result_text": [block.model_dump(mode="json") for block in result.content],
            }
        if binding in ("submit_diagnosis", "submit_mitigation"):
            # Real defect found and fixed forward this session: the real
            # sregym submit MCP server (mcp_server/submit_server.py) exposes
            # exactly ONE real tool, named "submit", taking a single free-
            # text argument `ans` -- confirmed live
            # (`fastmcp.exceptions.ToolError: Unknown tool: submit_diagnosis`)
            # and cross-checked against a real working client
            # (clients/demo/driver.py's manual_submit_tool, which calls
            # `call_tool("submit", {"ans": ...})`). There is no separate
            # `submit_diagnosis`/`submit_mitigation` tool in the real
            # benchmark -- SREGym's real grading model is one free-text
            # answer, not two typed submissions. This class's own two
            # `Capability` bindings are kept (a real caller may still
            # conceptually distinguish "I am submitting my diagnosis" from
            # "I am submitting my mitigation") but both now call the one
            # real tool with `payload` rendered as a single real text
            # answer via `_render_submit_answer`, matching what the real
            # benchmark actually accepts.
            ans = _render_submit_answer(binding, payload)
            async with _open_client_with_retry(
                lambda: Client(self._submit_mcp_url), label="submit_client"
            ) as submit_client:
                result = await submit_client.call_tool("submit", {"ans": ans})
            after = self._safe_status()
            return {
                "before": before,
                "after": after,
                "result_text": [block.model_dump(mode="json") for block in result.content],
            }
        if binding in ("observe_cluster_state", "get_benchmark_status"):
            return {"before": before, "after": self._safe_status()}
        # Real Jaeger/Loki/Prometheus MCP dispatch -- same
        # `_open_client_with_retry`/`call_tool(...)` pattern as
        # `run_kubectl`/`submit` above, `payload` passed straight through
        # as the real tool's own kwargs (each tool's exact real argument
        # names are documented on its own `Capability.title` above and
        # confirmed directly against the real vendored
        # `mcp_server/{jaeger,loki,prometheus}_server.py`).
        if binding.startswith("jaeger_"):
            tool_name = binding.removeprefix("jaeger_")
            async with _open_client_with_retry(
                lambda: Client(self._jaeger_mcp_url), label="jaeger_client"
            ) as jaeger_client:
                result = await jaeger_client.call_tool(tool_name, payload)
            after = self._safe_status()
            return {
                "before": before,
                "after": after,
                "result_text": [block.model_dump(mode="json") for block in result.content],
            }
        if binding.startswith("loki_"):
            tool_name = binding.removeprefix("loki_")
            async with _open_client_with_retry(
                lambda: Client(self._loki_mcp_url), label="loki_client"
            ) as loki_client:
                result = await loki_client.call_tool(tool_name, payload)
            after = self._safe_status()
            return {
                "before": before,
                "after": after,
                "result_text": [block.model_dump(mode="json") for block in result.content],
            }
        if binding.startswith("prometheus_"):
            tool_name = binding.removeprefix("prometheus_")
            async with _open_client_with_retry(
                lambda: Client(self._prometheus_mcp_url), label="prometheus_client"
            ) as prometheus_client:
                result = await prometheus_client.call_tool(tool_name, payload)
            after = self._safe_status()
            return {
                "before": before,
                "after": after,
                "result_text": [block.model_dump(mode="json") for block in result.content],
            }
        raise ValueError(f"unsupported sregym binding: {binding}")

    async def verify(self, expected: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
        """Poll the real conductor `/status` endpoint until it matches
        `expected` (e.g. a real stage transition) or a bounded timeout
        elapses -- never trusts a single `/status` read as convergence.

        Real defect found and fixed forward this session: a single
        transient `/status` read failure (real, live:
        `httpx.ReadTimeout: timed out` on one 10s-bounded poll, deep into
        this loop, well within the overall verify budget) previously
        crashed the whole `verify()` call instead of being treated as
        "not yet observed, keep polling" -- confirmed live, on a run that
        had already made real progress through every prior real pipeline
        step (observe, both real submissions, real remediation) and was
        only lost on this very last, transient hiccup. `_status()`
        failures inside this loop are now caught and treated as a
        non-matching observation, same as a real stage that simply hasn't
        transitioned yet -- the bounded deadline (not a swallowed
        exception) is still what ends the loop."""
        self._ensure_open()

        def _poll() -> dict[str, Any]:
            try:
                return self._status()
            except Exception:  # noqa: BLE001 -- a transient real network hiccup during polling is not a fatal verify() failure; the bounded deadline below still ends the loop
                return {}

        observed: dict[str, Any] = {}

        def _check() -> bool:
            nonlocal observed
            observed = _poll()
            return all(observed.get(key) == value for key, value in expected.items())

        passed = poll_until(
            _check,
            timeout_seconds=self._verify_timeout,
            interval_seconds=_POLL_INTERVAL_SECONDS,
        )
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

    def _kill_process_group(self, wait_timeout: float) -> None:
        """Real, shared teardown-of-a-real-process-tree helper. Signals the
        WHOLE process group (`self._process` was started with
        `start_new_session=True`), not just the one PID captured by
        `self._process`, so main.py's own real Docker container + `kubectl
        port-forward` children are actually reaped instead of surviving as
        real orphans -- confirmed live this session as a real, separate
        defect: the startup-timeout path (`_startup_check`'s caller) used
        to call bare `self._process.kill()` instead of this, and every
        timed-out materialize() left a real `docker run --cpus=4.0
        --memory=8g ...` container and port-forward running, which then
        starved a LATER materialize() attempt of real CPU/memory on this
        machine -- a real, observed cascading failure, not a hypothetical
        one. `os.killpg` on a pgid that's already gone raises
        `ProcessLookupError` -- swallowed, since that only means the whole
        group already exited."""
        pgid = None
        try:
            pgid = os.getpgid(self._process.pid)
        except ProcessLookupError:
            pass
        if pgid is not None:
            try:
                os.killpg(pgid, signal.SIGTERM)
            except ProcessLookupError:
                pass
        try:
            self._process.wait(timeout=wait_timeout)
        except subprocess.TimeoutExpired:
            if pgid is not None:
                try:
                    os.killpg(pgid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            else:
                self._process.kill()
            self._process.wait(timeout=10.0)

    async def teardown(self) -> None:
        if self._closed:
            return
        try:
            # No persistent client state to close anymore -- every real
            # actuate() call already opened, used, and closed its own
            # client via _open_client_with_retry.
            self._kill_process_group(self._teardown_timeout)
        finally:
            # Real defect found and fixed forward this session: `wait()`
            # reaps the process but never closed the real `stdout`/`stderr`
            # PIPE file objects `__init__` used to open (before the
            # log-file redirect below existed) -- on the normal
            # (non-startup-failure) path `communicate()` was never called
            # either, so those two real file descriptors leaked past
            # teardown, confirmed live via a real
            # `PytestUnraisableExceptionWarning` naming two real
            # `_io.FileIO` objects at session cleanup. `Popen.stdout`/
            # `.stderr` are always `None` now (stdout/stderr are redirected
            # to `self._log_fh`, not PIPE) -- these two closes are now
            # dead code in practice but harmless (`is not None` guards
            # them) and cost nothing to leave for any caller still on the
            # old PIPE-based construction path.
            if self._process.stdout is not None:
                self._process.stdout.close()
            if self._process.stderr is not None:
                self._process.stderr.close()
            # `getattr` -- some tests construct `SregymEnvironment` via
            # `object.__new__` and manually set only `_process`/`_closed`/
            # `_teardown_timeout`, bypassing `__init__` (and therefore
            # `_log_fh`) entirely; `teardown()` must still work for them.
            log_fh = getattr(self, "_log_fh", None)
            if log_fh is not None:
                log_fh.close()
            self._closed = True

    def is_really_stopped(self) -> bool:
        """Real post-teardown confirmation helper for tests: queries the
        real subprocess's own exit status directly rather than trusting
        `teardown()`'s own bookkeeping."""
        return self._process.poll() is not None


def _resolve_materialize_argv_and_env(
    *, scenario: str | None, config: dict[str, Any]
) -> tuple[list[str], dict[str, str], dict[str, Any]]:
    """Pure config-resolution step of `SregymVendorProvider.materialize()`,
    extracted so argv/env construction is directly unit-testable without a
    real pinned checkout, a real subprocess, or a live cluster -- matching
    this module's existing pattern of small testable functions
    (`_build_env`/`_build_full_subprocess_env`). Returns `(argv, env,
    resolved)` where `resolved` carries every other value `materialize()`
    needs to construct `SregymEnvironment` (ports, timeouts, requires_authority)."""
    agent_name = config.get("agent_name", "debug")
    if not isinstance(agent_name, str) or not agent_name:
        raise TypeError("config.agent_name must be a non-empty string")
    # Real defect fixed forward this session: this default previously
    # named an "openai/..." litellm provider prefix, which forces litellm
    # to require a real OPENAI_API_KEY regardless of what's actually
    # exported in the environment -- confirmed live (a real trial crashed
    # with `litellm.AuthenticationError: ... OPENAI_API_KEY ...` even
    # though this repo has no OpenAI credential anywhere and GROQ_API_KEY
    # was exported and confirmed forwarded via `_build_full_subprocess_env`).
    # `autofde-lab`'s own driver (`gymact_diagnosis_driver.py`) already
    # passes an explicit, real, working Groq-hosted model id for every
    # live trial (`groq/openai/gpt-oss-20b`, confirmed against the real
    # Groq `/v1/models` listing this session) -- this default now matches
    # it, so a caller that omits `judge_model_id` entirely (e.g. this
    # module's own test suite) resolves to Groq, never OpenAI, matching
    # every other credential this repo forwards.
    judge_model_id = config.get("judge_model_id", "groq/openai/gpt-oss-20b")
    if not isinstance(judge_model_id, str) or not judge_model_id:
        raise TypeError("config.judge_model_id must be a non-empty string")
    problem_id = config.get("problem_id", scenario or "misconfig_app_hotel_res")
    if not isinstance(problem_id, str) or not problem_id:
        raise TypeError("config.problem_id must be a non-empty string")
    wall_clock_timeout_s = config.get("wall_clock_timeout_s", 600)
    if isinstance(wall_clock_timeout_s, bool) or not isinstance(wall_clock_timeout_s, int):
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
        agent_name=agent_name,
        judge_model_id=judge_model_id,
        problem_id=problem_id,
        wall_clock_timeout_s=int(wall_clock_timeout_s),
    )
    env = _build_env(
        judge_api_base=judge_api_base,
        judge_api_key_placeholder=judge_api_key_placeholder,
    )
    resolved = {
        "mcp_server_port": int(mcp_server_port),
        "api_port": int(api_port),
        "startup_timeout_seconds": float(startup_timeout_seconds),
        "verify_timeout_seconds": float(verify_timeout_seconds),
        "teardown_timeout_seconds": float(teardown_timeout_seconds),
        "requires_authority": requires_authority,
    }
    return argv, env, resolved


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
        root_value = config.get("root")
        if root_value is not None and not isinstance(root_value, str):
            raise TypeError("config.root must be a string path when supplied")
        # Not `vendor_benchmarks.vendor_root("sregym")`: that helper looks
        # `"sregym"` up in the shared, lock-derived `VENDOR_SPECS` dict, which
        # deliberately does not contain a `"sregym"` entry (see `_SPEC`'s own
        # comment above). `_SPEC.relative_root` (`vendor/gyms/sregym`) is the
        # same real layout `vendor_root()` would produce; only the lab-root
        # resolution is reproduced locally here.
        root = Path(root_value).expanduser() if root_value else _default_root()

        audit = _audit_spec(_SPEC, root)
        if audit.standing != "PARTIAL_ALIVE":
            raise VendorAdmissionError(audit.reason, str(audit.root))

        argv, env, resolved = _resolve_materialize_argv_and_env(
            scenario=scenario, config=config
        )

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None,
            lambda: SregymEnvironment(
                root=audit.root,
                argv=argv,
                env=env,
                mcp_server_port=resolved["mcp_server_port"],
                api_port=resolved["api_port"],
                startup_timeout_seconds=resolved["startup_timeout_seconds"],
                verify_timeout_seconds=resolved["verify_timeout_seconds"],
                teardown_timeout_seconds=resolved["teardown_timeout_seconds"],
                requires_authority=resolved["requires_authority"],
            ),
        )
