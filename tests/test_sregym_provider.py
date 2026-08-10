"""Chicago-style tests for `gymact.gyms.sregym`.

No mocks: `test_wrong_revision_is_refused_before_materialization` needs no
live cluster or subprocess -- it exercises the real `_audit_spec` git-pin
check against a real, throwaway git checkout (matching
`test_vendor_benchmarks.py`'s own `test_wrong_revision_is_refused_before_materialization`
pattern). The live-materialization test is real end-to-end (real
`sregym` `main.py` subprocess, real MCP client, real `kubectl`) and
degrades to a named, visible skip -- never a mock substitute -- when its
real prerequisites (reachable cluster, exact-pinned real sregym checkout)
are not present in this environment.
"""

from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from gymact.gyms.sregym import (
    SREGYM_CAPABILITIES,
    SregymVendorProvider,
    _build_argv,
    _build_full_subprocess_env,
    _resolve_materialize_argv_and_env,
)
from gymact.gyms.vendor_benchmarks import VendorAdmissionError, VendorSpec, _audit_spec


def _autofde_lab_root() -> Path:
    configured = os.environ.get("AUTOFDE_LAB")
    return Path(configured).expanduser() if configured else Path.home() / "autofde-lab"


def _real_sregym_checkout_ready() -> tuple[bool, str]:
    """Real, honest gating for the live test: reachable cluster AND an
    exact-pinned real sregym checkout AND a real kubectl binary."""
    if shutil.which("kubectl") is None:
        return False, "kubectl binary not found on PATH"
    cluster_info = subprocess.run(
        ["kubectl", "cluster-info"], capture_output=True, text=True, timeout=10.0
    )
    if cluster_info.returncode != 0:
        return False, f"no reachable kubernetes cluster: {cluster_info.stderr.strip()[:200]}"
    lab_root = _autofde_lab_root()
    sregym_root = lab_root / "vendor" / "gyms" / "sregym"
    if not sregym_root.is_dir():
        return False, f"real sregym checkout not present at {sregym_root}"
    if not (sregym_root / "main.py").is_file():
        return False, f"sregym checkout at {sregym_root} has no main.py"
    from gymact.gyms.vendor_benchmarks import VENDOR_SPECS

    audit = _audit_spec(VENDOR_SPECS["sregym"], sregym_root)
    if audit.standing != "PARTIAL_ALIVE":
        return False, f"sregym checkout not at pinned revision: {audit.reason}"
    return True, "ready"


class SregymSubprocessEnvTests(unittest.TestCase):
    """Real regression test for the env-replacement defect found and fixed
    forward this session: `subprocess.Popen(env=...)` replaces the child's
    entire environment rather than merging with the parent's, so
    `SregymEnvironment.__init__` must build its `full_env` on top of a real
    base environment, not construct one from scratch. No subprocess or
    cluster needed -- this exercises the pure merge function directly."""

    def test_base_env_keys_survive_into_full_env(self):
        base = {"GROQ_API_KEY": "gsk_real_key_value", "PATH": "/usr/bin:/bin"}
        result = _build_full_subprocess_env(
            base_env=base, mcp_server_port=9954, api_port=8000, overrides={}
        )
        self.assertEqual(result["GROQ_API_KEY"], "gsk_real_key_value")
        self.assertEqual(result["PATH"], "/usr/bin:/bin")

    def test_port_keys_and_overrides_still_win_over_base_env(self):
        base = {"MCP_SERVER_PORT": "1", "API_PORT": "2", "AGENT_API_KEY": "stale"}
        result = _build_full_subprocess_env(
            base_env=base,
            mcp_server_port=9955,
            api_port=8001,
            overrides={"AGENT_API_KEY": "fresh"},
        )
        self.assertEqual(result["MCP_SERVER_PORT"], "9955")
        self.assertEqual(result["API_PORT"], "8001")
        self.assertEqual(result["AGENT_API_KEY"], "fresh")

    def test_real_os_environ_is_a_valid_base(self):
        """Proves the actual production call shape (dict(os.environ) as
        base_env) works end to end, not just a hand-constructed dict."""
        import os

        result = _build_full_subprocess_env(
            base_env=dict(os.environ), mcp_server_port=1, api_port=2, overrides={}
        )
        # A real, always-present env var on any POSIX process -- proves
        # os.environ's real content actually made it into the result.
        self.assertIn("PATH", result)


class SregymEnvironmentStartupErrorMessageTests(unittest.TestCase):
    """Real regression test for the diagnostic-loss defect found and fixed
    forward this session: the RuntimeError raised when the real subprocess
    exits during startup previously included only stderr, silently dropping
    main.py's own rich-logged stdout diagnostics -- confirmed live, more
    than once, when the raised message was empty/unhelpful while the real
    cause sat in stdout. Uses a real throwaway Python script as the fake
    main.py (a real subprocess, real exit, real captured output) rather
    than sregym's own main.py, so this is fast and needs no cluster."""

    def test_stdout_is_included_when_subprocess_exits_during_startup(self):
        from gymact.gyms.sregym import SregymEnvironment

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fake_main = root / "main.py"
            fake_main.write_text(
                "import sys\n"
                "print('DISTINCTIVE_STDOUT_MARKER: real diagnostic here')\n"
                "sys.exit(0)\n",
                encoding="utf-8",
            )
            with self.assertRaises(RuntimeError) as ctx:
                SregymEnvironment(
                    root=root,
                    argv=["python3", str(fake_main)],
                    env={},
                    mcp_server_port=1,
                    api_port=2,
                    startup_timeout_seconds=5.0,
                    verify_timeout_seconds=5.0,
                    teardown_timeout_seconds=5.0,
                )
            self.assertIn("DISTINCTIVE_STDOUT_MARKER", str(ctx.exception))


class SregymBuildArgvAgentNameTests(unittest.TestCase):
    """Real string assertions on `_build_argv`'s agent_name threading -- no
    subprocess needed. Regression coverage for THREE real, empirically
    disproven hypotheses this session, in order: `autofde_lab_planner`
    (driver module missing on disk), `autofde_lab_dspy` (real driver, but
    runs to completion and exits -- SregymEnvironment never gets external
    control), `--use-external-harness` (exits immediately after fault
    injection). `"debug"` (a real, pre-existing agents.yaml no-op,
    `signal.pause()`) is the confirmed-live-working default: the conductor
    stays up, real HTTP `/status` answered `{"stage":"diagnosis"}` while it
    ran, waiting for this module's own `actuate()` to submit externally."""

    def test_explicit_agent_name_is_threaded_into_argv(self):
        argv = _build_argv(
            agent_name="autofde_lab_dspy",
            judge_model_id="openai/gemma-4-26b-a4b-it",
            problem_id="misconfig_app_hotel_res",
            wall_clock_timeout_s=600,
        )
        self.assertIn("--agent", argv)
        self.assertEqual(argv[argv.index("--agent") + 1], "autofde_lab_dspy")

    def test_default_agent_name_is_debug(self):
        argv = _build_argv(
            judge_model_id="openai/gemma-4-26b-a4b-it",
            problem_id="misconfig_app_hotel_res",
            wall_clock_timeout_s=600,
        )
        self.assertEqual(argv[argv.index("--agent") + 1], "debug")

    def test_autofde_lab_planner_remains_explicitly_selectable(self):
        """The missing driver module is a real, independent defect in the
        sibling repo -- this module must not remove the ability to request
        `autofde_lab_planner` explicitly."""
        argv = _build_argv(
            agent_name="autofde_lab_planner",
            judge_model_id="openai/gemma-4-26b-a4b-it",
            problem_id="misconfig_app_hotel_res",
            wall_clock_timeout_s=600,
        )
        self.assertEqual(argv[argv.index("--agent") + 1], "autofde_lab_planner")


class SregymResolveMaterializeConfigTests(unittest.TestCase):
    """Proves `SregymVendorProvider.materialize()`'s real config-resolution
    step threads `agent_name` from `config` into the constructed argv,
    without needing a live cluster, a real pinned checkout, or a real
    subprocess -- exercises the exact pure function `materialize()` calls."""

    def test_default_config_threads_debug_into_argv(self):
        argv, env, resolved = _resolve_materialize_argv_and_env(
            scenario="misconfig_app_hotel_res", config={}
        )
        self.assertEqual(argv[argv.index("--agent") + 1], "debug")
        self.assertIsInstance(env, dict)
        self.assertTrue(resolved["requires_authority"])

    def test_config_agent_name_overrides_default_in_argv(self):
        argv, _env, _resolved = _resolve_materialize_argv_and_env(
            scenario="misconfig_app_hotel_res",
            config={"agent_name": "autofde_lab_planner"},
        )
        self.assertEqual(argv[argv.index("--agent") + 1], "autofde_lab_planner")

    def test_invalid_agent_name_type_is_rejected(self):
        with self.assertRaises(TypeError):
            _resolve_materialize_argv_and_env(
                scenario=None, config={"agent_name": 123}
            )


class SregymProviderAdmissionTests(unittest.TestCase):
    def _real_checkout(self):
        tmp = tempfile.TemporaryDirectory()
        root = Path(tmp.name)
        subprocess.run(["git", "init", "-q", str(root)], check=True)
        subprocess.run(
            ["git", "-C", str(root), "config", "user.email", "gymact@example.invalid"],
            check=True,
        )
        subprocess.run(
            ["git", "-C", str(root), "config", "user.name", "GymAct Test"], check=True
        )
        marker = root / "main.py"
        marker.write_text("print('not the real sregym')\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(root), "add", "main.py"], check=True)
        subprocess.run(
            ["git", "-C", str(root), "commit", "-qm", "fixture collaborator"], check=True
        )
        return tmp, root

    def test_capabilities_are_real_typed_objects(self):
        bindings = {capability.binding for capability in SREGYM_CAPABILITIES}
        self.assertEqual(
            bindings,
            {
                "observe_cluster_state",
                "run_kubectl",
                "submit_diagnosis",
                "submit_mitigation",
                "get_benchmark_status",
            },
        )

    def test_wrong_revision_is_refused_before_materialization(self):
        """Matches `test_vendor_benchmarks.py`'s
        `test_wrong_revision_is_refused_before_materialization`: a real git
        checkout at the wrong HEAD is REFUSED by the real, shared
        `_audit_spec` pin check -- no subprocess, no cluster, no MCP client
        is ever started."""
        tmp, root = self._real_checkout()
        try:
            wrong_spec = VendorSpec("sregym", "0" * 40)
            audit = _audit_spec(wrong_spec, root)
            self.assertEqual(audit.standing, "REFUSED")
            self.assertEqual(audit.reason, "REFUSED:VENDOR_REVISION_MISMATCH")

            provider = SregymVendorProvider()
            with self.assertRaises(VendorAdmissionError) as ctx:
                asyncio.run(
                    provider.materialize(scenario=None, config={"root": str(root)})
                )
            self.assertEqual(ctx.exception.code, "REFUSED:VENDOR_REVISION_MISMATCH")
        finally:
            tmp.cleanup()

    def test_git_checkout_missing_is_blocked(self):
        provider = SregymVendorProvider()
        missing_root = Path(tempfile.mkdtemp()) / "does-not-exist"
        with self.assertRaises(VendorAdmissionError) as ctx:
            asyncio.run(
                provider.materialize(scenario=None, config={"root": str(missing_root)})
            )
        self.assertEqual(ctx.exception.code, "BLOCKED:VENDOR_CHECKOUT_MISSING")


_LIVE_READY, _LIVE_REASON = _real_sregym_checkout_ready()


@unittest.skipUnless(
    _LIVE_READY,
    f"live sregym prerequisites not met: {_LIVE_REASON}",
)
class SregymProviderLiveEpisodeTests(unittest.TestCase):
    """Real end-to-end: real sregym `main.py` subprocess, real persistent
    `fastmcp.Client` MCP session, real `kubectl get namespaces` through
    sregym's real `kubectl-mcp` server. Named skip (never a mock) when the
    real prerequisites above are not met in this environment."""

    def test_real_materialize_observe_and_read_only_kubectl_actuate(self):
        provider = SregymVendorProvider()
        environment = asyncio.run(
            provider.materialize(
                scenario="misconfig_app_hotel_res",
                config={"wall_clock_timeout_s": 600},
            )
        )
        try:
            observation = asyncio.run(environment.observe())
            self.assertIsInstance(observation, dict)

            run_kubectl = next(
                capability
                for capability in environment.capabilities()
                if capability.binding == "run_kubectl"
            )
            result = asyncio.run(
                environment.actuate(
                    run_kubectl, {"command": "kubectl get namespaces"}
                )
            )
            self.assertIn("result_text", result)
            self.assertTrue(len(result["result_text"]) > 0)
        finally:
            asyncio.run(environment.teardown())
            self.assertTrue(environment.is_really_stopped())


if __name__ == "__main__":
    unittest.main()
