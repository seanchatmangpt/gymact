from __future__ import annotations

import asyncio
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from gymact.gyms.vendor_benchmarks import (
    LOCK_SOURCE_SHA,
    VENDOR_PROVIDERS,
    VENDOR_REVISIONS,
    VendorAdmissionError,
    VendorBenchmarkProvider,
    VendorSpec,
    audit_vendor,
)


class VendorBenchmarkProviderTests(unittest.TestCase):
    def test_current_lock_has_exact_provider_for_every_pinned_vendor(self):
        self.assertEqual(LOCK_SOURCE_SHA, "dcc9947f713a719d9c0952f90b95b3f12a2f2cbe")
        # 52, not 51: this session added "awesome-ai-gyms" (see gym_index.py)
        # as the 52nd pinned vendor entry, matching the existing pin-by-SHA
        # convention every other vendor here already uses.
        self.assertEqual(len(VENDOR_REVISIONS), 52)
        self.assertEqual(set(VENDOR_PROVIDERS), set(VENDOR_REVISIONS))
        self.assertTrue(all(len(revision) == 40 for revision in VENDOR_REVISIONS.values()))
        self.assertTrue(all(revision == revision.lower() for revision in VENDOR_REVISIONS.values()))

    def _real_checkout(self):
        tmp = tempfile.TemporaryDirectory()
        root = Path(tmp.name)
        subprocess.run(["git", "init", "-q", str(root)], check=True)
        subprocess.run(
            ["git", "-C", str(root), "config", "user.email", "gymact@example.invalid"],
            check=True,
        )
        subprocess.run(
            ["git", "-C", str(root), "config", "user.name", "GymAct Test"],
            check=True,
        )
        runner = root / "vendor_runner.py"
        runner.write_text(
            'import sys\nprint(f"real-vendor:{sys.argv[1]}")\n', encoding="utf-8"
        )
        subprocess.run(["git", "-C", str(root), "add", "vendor_runner.py"], check=True)
        subprocess.run(
            ["git", "-C", str(root), "commit", "-qm", "fixture collaborator"], check=True
        )
        revision = subprocess.check_output(
            ["git", "-C", str(root), "rev-parse", "HEAD"], text=True
        ).strip()
        return tmp, root, revision

    def test_exact_git_checkout_executes_real_native_process_without_shell(self):
        tmp, root, revision = self._real_checkout()
        try:
            provider = VendorBenchmarkProvider("agentbench")
            provider.spec = VendorSpec("agentbench", revision)
            environment = asyncio.run(
                provider.materialize(
                    scenario=None,
                    config={"root": str(root), "timeout_seconds": 5},
                )
            )
            result = asyncio.run(
                environment.run_native(["python3", "vendor_runner.py", "episode-1"])
            )
            self.assertEqual(result["returncode"], 0)
            self.assertEqual(result["stdout"], "real-vendor:episode-1\n")
            self.assertEqual(result["revision"], revision)
            asyncio.run(environment.teardown())
        finally:
            tmp.cleanup()

    def test_wrong_revision_is_refused_before_materialization(self):
        tmp, root, _revision = self._real_checkout()
        try:
            audit = audit_vendor("agentbench", root=root)
            self.assertEqual(audit.standing, "REFUSED")
            self.assertEqual(audit.reason, "REFUSED:VENDOR_REVISION_MISMATCH")
        finally:
            tmp.cleanup()

    def test_command_cannot_escape_vendor_root(self):
        tmp, root, revision = self._real_checkout()
        try:
            provider = VendorBenchmarkProvider("agentbench")
            provider.spec = VendorSpec("agentbench", revision)
            environment = asyncio.run(
                provider.materialize(scenario=None, config={"root": str(root)})
            )
            with self.assertRaisesRegex(
                VendorAdmissionError, "REFUSED:COMMAND_ESCAPES_VENDOR_ROOT"
            ):
                asyncio.run(environment.run_native(["../outside-command"]))
        finally:
            tmp.cleanup()

    def test_real_lab_checkout_is_audited_when_present(self):
        lab = os.environ.get("AUTOFDE_LAB")
        if not lab or not Path(lab).is_dir():
            self.skipTest("AUTOFDE_LAB real collaborator checkout is not present")
        for name in sorted(VENDOR_REVISIONS):
            root = Path(lab) / "vendor" / "gyms" / name
            if not root.exists():
                continue
            audit = audit_vendor(name, root=root)
            self.assertEqual(audit.standing, "PARTIAL_ALIVE", f"{name}: {audit}")


if __name__ == "__main__":
    unittest.main()
