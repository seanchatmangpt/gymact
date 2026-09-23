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
    VENDOR_SPECS,
    VendorAdmissionError,
    VendorBenchmarkProvider,
    VendorSpec,
    audit_all_vendors,
    audit_vendor,
    provider_for_vendor,
    register_vendor_providers,
    vendor_root,
)


class _FakeRuntime:
    def __init__(self) -> None:
        self.registered: list[VendorBenchmarkProvider] = []

    def register_provider(self, provider: VendorBenchmarkProvider) -> None:
        self.registered.append(provider)


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
        runner.write_text('import sys\nprint(f"real-vendor:{sys.argv[1]}")\n', encoding="utf-8")
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

            # observe() reflects the last real result.
            observed = asyncio.run(environment.observe())
            self.assertEqual(observed["vendor"], "agentbench")
            self.assertEqual(observed["last_result"]["returncode"], 0)

            # capabilities() exposes a single DO run-native capability.
            caps = environment.capabilities()
            self.assertEqual(len(caps), 1)
            self.assertEqual(caps[0].binding, "run-native")

            # actuate() dispatches to run_native via the capability binding.
            actuate_result = asyncio.run(
                environment.actuate(caps[0], {"argv": ["python3", "vendor_runner.py", "ep-2"]})
            )
            self.assertEqual(actuate_result["stdout"], "real-vendor:ep-2\n")

            # verify() checks observed state against expectations.
            passed, observed_after = asyncio.run(environment.verify({"vendor": "agentbench"}))
            self.assertTrue(passed)
            self.assertEqual(observed_after["vendor"], "agentbench")

            # checkpoint()/restore() round-trip the last real result.
            checkpoint = asyncio.run(environment.checkpoint())
            self.assertEqual(checkpoint["revision"], revision)
            asyncio.run(environment.restore(checkpoint))

            asyncio.run(environment.teardown())

            # Using the environment after teardown raises.
            with self.assertRaises(RuntimeError):
                asyncio.run(environment.observe())
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

    def test_wrong_revision_refuses_materialize_with_real_checkout(self):
        tmp, root, _revision = self._real_checkout()
        try:
            provider = VendorBenchmarkProvider("agentbench")
            with self.assertRaisesRegex(VendorAdmissionError, "REFUSED:VENDOR_REVISION_MISMATCH"):
                asyncio.run(provider.materialize(scenario=None, config={"root": str(root)}))
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

    # -- Missing / non-git checkout error paths -------------------------------

    def test_missing_checkout_directory_is_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "does-not-exist"
            audit = audit_vendor("agentbench", root=missing)
            self.assertEqual(audit.standing, "BLOCKED")
            self.assertEqual(audit.reason, "BLOCKED:VENDOR_CHECKOUT_MISSING")

    def test_materialize_against_missing_checkout_raises_blocked(self):
        provider = VendorBenchmarkProvider("agentbench")
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "does-not-exist"
            with self.assertRaisesRegex(VendorAdmissionError, "BLOCKED:VENDOR_CHECKOUT_MISSING"):
                asyncio.run(provider.materialize(scenario=None, config={"root": str(missing)}))

    def test_non_git_directory_is_refused_as_not_git(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "readme.txt").write_text("not a git repo", encoding="utf-8")
            audit = audit_vendor("agentbench", root=root)
            self.assertEqual(audit.standing, "REFUSED")
            self.assertEqual(audit.reason, "REFUSED:VENDOR_CHECKOUT_NOT_GIT")

    def test_git_unavailable_is_blocked_with_real_empty_path(self):
        old_path = os.environ.get("PATH", "")
        with tempfile.TemporaryDirectory() as empty_bin, tempfile.TemporaryDirectory() as root:
            os.environ["PATH"] = empty_bin
            try:
                audit = audit_vendor("agentbench", root=Path(root))
                self.assertEqual(audit.standing, "BLOCKED")
                self.assertEqual(audit.reason, "BLOCKED:GIT_UNAVAILABLE")
            finally:
                os.environ["PATH"] = old_path

    # -- Command traversal / argv validation -----------------------------------

    def test_safe_argv_rejects_empty_list(self):
        provider = VendorBenchmarkProvider("agentbench")
        tmp, root, revision = self._real_checkout()
        try:
            provider.spec = VendorSpec("agentbench", revision)
            environment = asyncio.run(
                provider.materialize(scenario=None, config={"root": str(root)})
            )
            with self.assertRaises(TypeError):
                asyncio.run(environment.run_native([]))
            with self.assertRaises(TypeError):
                asyncio.run(environment.run_native("not-a-list"))
            with self.assertRaises(TypeError):
                asyncio.run(environment.run_native(["", "arg"]))
        finally:
            tmp.cleanup()

    def test_absolute_argv_executable_is_refused(self):
        provider = VendorBenchmarkProvider("agentbench")
        tmp, root, revision = self._real_checkout()
        try:
            provider.spec = VendorSpec("agentbench", revision)
            environment = asyncio.run(
                provider.materialize(scenario=None, config={"root": str(root)})
            )
            with self.assertRaisesRegex(
                VendorAdmissionError, "REFUSED:COMMAND_ESCAPES_VENDOR_ROOT"
            ):
                asyncio.run(environment.run_native(["/bin/echo", "hi"]))
        finally:
            tmp.cleanup()

    # -- Native command absence / timeout / drift ------------------------------

    def test_native_command_absence_is_blocked(self):
        tmp, root, revision = self._real_checkout()
        try:
            provider = VendorBenchmarkProvider("agentbench")
            provider.spec = VendorSpec("agentbench", revision)
            environment = asyncio.run(
                provider.materialize(scenario=None, config={"root": str(root)})
            )
            with self.assertRaisesRegex(VendorAdmissionError, "BLOCKED:NATIVE_COMMAND_UNAVAILABLE"):
                asyncio.run(environment.run_native(["definitely-not-a-real-binary-xyz"]))
        finally:
            tmp.cleanup()

    def test_native_command_timeout_is_blocked(self):
        tmp, root, revision = self._real_checkout()
        try:
            provider = VendorBenchmarkProvider("agentbench")
            provider.spec = VendorSpec("agentbench", revision)
            environment = asyncio.run(
                provider.materialize(
                    scenario=None,
                    config={"root": str(root), "timeout_seconds": 0.05},
                )
            )
            with self.assertRaisesRegex(VendorAdmissionError, "BLOCKED:NATIVE_COMMAND_TIMEOUT"):
                asyncio.run(environment.run_native(["sleep", "5"]))
        finally:
            tmp.cleanup()

    def test_revision_drift_before_run_is_refused(self):
        tmp, root, revision = self._real_checkout()
        try:
            provider = VendorBenchmarkProvider("agentbench")
            provider.spec = VendorSpec("agentbench", revision)
            environment = asyncio.run(
                provider.materialize(scenario=None, config={"root": str(root)})
            )
            # Mutate the real checkout's HEAD for real, after materialize admitted it.
            (root / "extra.txt").write_text("drift", encoding="utf-8")
            subprocess.run(["git", "-C", str(root), "add", "extra.txt"], check=True)
            subprocess.run(["git", "-C", str(root), "commit", "-qm", "drift commit"], check=True)
            with self.assertRaisesRegex(VendorAdmissionError, "REFUSED:VENDOR_REVISION_DRIFT"):
                asyncio.run(environment.run_native(["python3", "vendor_runner.py", "x"]))
        finally:
            tmp.cleanup()

    def test_revision_drift_during_run_is_refused_after_command_completes(self):
        tmp, root, revision = self._real_checkout()
        try:
            provider = VendorBenchmarkProvider("agentbench")
            provider.spec = VendorSpec("agentbench", revision)
            environment = asyncio.run(
                provider.materialize(scenario=None, config={"root": str(root)})
            )
            commit_during_run = (
                "import subprocess\n"
                "open('drift-during-run.txt', 'w').write('x')\n"
                "subprocess.run(['git', 'add', 'drift-during-run.txt'], check=True)\n"
                "subprocess.run(['git', 'commit', '-qm', 'drift-during-run'], check=True)\n"
            )
            with self.assertRaisesRegex(VendorAdmissionError, "REFUSED:VENDOR_REVISION_DRIFT"):
                asyncio.run(environment.run_native(["python3", "-c", commit_during_run]))
        finally:
            tmp.cleanup()

    def test_git_revision_returns_none_when_git_binary_is_absent(self):
        old_path = os.environ.get("PATH", "")
        with tempfile.TemporaryDirectory() as empty_bin, tempfile.TemporaryDirectory() as root:
            os.environ["PATH"] = empty_bin
            try:
                from gymact.gyms.vendor_benchmarks import _git_revision

                self.assertIsNone(_git_revision(Path(root)))
            finally:
                os.environ["PATH"] = old_path

    # -- Checkpoint / restore mismatch ------------------------------------------

    def test_restore_with_mismatched_revision_is_refused(self):
        tmp, root, revision = self._real_checkout()
        try:
            provider = VendorBenchmarkProvider("agentbench")
            provider.spec = VendorSpec("agentbench", revision)
            environment = asyncio.run(
                provider.materialize(scenario=None, config={"root": str(root)})
            )
            with self.assertRaisesRegex(
                VendorAdmissionError, "REFUSED:CHECKPOINT_REVISION_MISMATCH"
            ):
                asyncio.run(environment.restore({"revision": "0" * 40, "last_result": {}}))
        finally:
            tmp.cleanup()

    def test_restore_with_non_mapping_last_result_raises_type_error(self):
        tmp, root, revision = self._real_checkout()
        try:
            provider = VendorBenchmarkProvider("agentbench")
            provider.spec = VendorSpec("agentbench", revision)
            environment = asyncio.run(
                provider.materialize(scenario=None, config={"root": str(root)})
            )
            with self.assertRaises(TypeError):
                asyncio.run(
                    environment.restore({"revision": revision, "last_result": "not-a-dict"})
                )
        finally:
            tmp.cleanup()

    def test_actuate_rejects_unsupported_binding(self):
        tmp, root, revision = self._real_checkout()
        try:
            provider = VendorBenchmarkProvider("agentbench")
            provider.spec = VendorSpec("agentbench", revision)
            environment = asyncio.run(
                provider.materialize(scenario=None, config={"root": str(root)})
            )

            class _FakeCapability:
                binding = "not-run-native"

            with self.assertRaises(ValueError):
                asyncio.run(environment.actuate(_FakeCapability(), {"argv": ["x"]}))
        finally:
            tmp.cleanup()

    # -- root path traversal guard (hardening) -----------------------------------

    def test_materialize_refuses_root_with_dotdot_traversal(self):
        provider = VendorBenchmarkProvider("agentbench")
        with self.assertRaisesRegex(VendorAdmissionError, "REFUSED:VENDOR_ROOT_TRAVERSAL"):
            asyncio.run(
                provider.materialize(
                    scenario=None,
                    config={"root": "/tmp/vendor-checkout/../../etc"},
                )
            )

    def test_materialize_refuses_root_with_relative_dotdot_traversal(self):
        provider = VendorBenchmarkProvider("agentbench")
        with self.assertRaisesRegex(VendorAdmissionError, "REFUSED:VENDOR_ROOT_TRAVERSAL"):
            asyncio.run(
                provider.materialize(
                    scenario=None,
                    config={"root": "vendor/gyms/../../../etc/passwd"},
                )
            )

    def test_materialize_accepts_clean_absolute_root(self):
        tmp, root, revision = self._real_checkout()
        try:
            provider = VendorBenchmarkProvider("agentbench")
            provider.spec = VendorSpec("agentbench", revision)
            environment = asyncio.run(
                provider.materialize(scenario=None, config={"root": str(root)})
            )
            self.assertEqual(Path(environment.root).resolve(), root.resolve())
        finally:
            tmp.cleanup()

    # -- config validation --------------------------------------------------------

    def test_materialize_rejects_non_string_root(self):
        provider = VendorBenchmarkProvider("agentbench")
        with self.assertRaises(TypeError):
            asyncio.run(provider.materialize(scenario=None, config={"root": 12345}))

    def test_materialize_rejects_invalid_timeout(self):
        tmp, root, revision = self._real_checkout()
        try:
            provider = VendorBenchmarkProvider("agentbench")
            provider.spec = VendorSpec("agentbench", revision)
            with self.assertRaises(TypeError):
                asyncio.run(
                    provider.materialize(
                        scenario=None,
                        config={"root": str(root), "timeout_seconds": -1},
                    )
                )
            with self.assertRaises(TypeError):
                asyncio.run(
                    provider.materialize(
                        scenario=None,
                        config={"root": str(root), "timeout_seconds": True},
                    )
                )
            with self.assertRaises(TypeError):
                asyncio.run(
                    provider.materialize(
                        scenario=None,
                        config={"root": str(root), "timeout_seconds": "5"},
                    )
                )
        finally:
            tmp.cleanup()

    # -- vendor lookup / registry helpers -----------------------------------------

    def test_unknown_vendor_raises_key_error(self):
        with self.assertRaises(KeyError):
            VendorBenchmarkProvider("not-a-real-vendor")
        with self.assertRaises(KeyError):
            audit_vendor("not-a-real-vendor")
        with self.assertRaises(KeyError):
            vendor_root("not-a-real-vendor")

    def test_vendor_root_uses_configured_lab_root(self):
        with tempfile.TemporaryDirectory() as lab:
            root = vendor_root("agentbench", lab_root=lab)
            self.assertEqual(root, Path(lab) / "vendor" / "gyms" / "agentbench")

    def test_default_lab_root_honors_autofde_lab_env_var(self):
        old = os.environ.get("AUTOFDE_LAB")
        try:
            os.environ["AUTOFDE_LAB"] = "/tmp/custom-lab-root"
            root = vendor_root("agentbench")
            self.assertEqual(root, Path("/tmp/custom-lab-root/vendor/gyms/agentbench"))
        finally:
            if old is None:
                os.environ.pop("AUTOFDE_LAB", None)
            else:
                os.environ["AUTOFDE_LAB"] = old

    def test_audit_all_vendors_covers_every_pinned_vendor(self):
        with tempfile.TemporaryDirectory() as lab:
            audits = audit_all_vendors(lab_root=lab)
            self.assertEqual(len(audits), len(VENDOR_SPECS))
            self.assertTrue(all(a.standing == "BLOCKED" for a in audits))

    def test_provider_for_vendor_returns_configured_provider(self):
        provider = provider_for_vendor("agentbench")
        self.assertIsInstance(provider, VendorBenchmarkProvider)
        self.assertEqual(provider.name, "agentbench")

    def test_register_vendor_providers_registers_selected_names(self):
        runtime = _FakeRuntime()
        registered = register_vendor_providers(runtime, names=("agentbench", "cybench"))
        self.assertEqual(registered, ("agentbench", "cybench"))
        self.assertEqual(len(runtime.registered), 2)
        self.assertEqual({p.name for p in runtime.registered}, {"agentbench", "cybench"})

    def test_register_vendor_providers_defaults_to_all_vendors(self):
        runtime = _FakeRuntime()
        registered = register_vendor_providers(runtime)
        self.assertEqual(registered, tuple(sorted(VENDOR_SPECS)))
        self.assertEqual(len(runtime.registered), len(VENDOR_SPECS))


if __name__ == "__main__":
    unittest.main()
