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

from gymact.gyms.sregym import SREGYM_CAPABILITIES, SregymVendorProvider
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
