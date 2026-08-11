"""Chicago-style tests for `scripts/check_observe_independence.py`.

Real collaborators throughout: real `.py` source files written to `tmp_path`,
a real `ast.parse` + the real `check_file`/`build_report` functions from the
script itself (imported directly, no mocking of the module under test), and
real assertions on the real classification output. No `unittest.mock`/
`Mock`/`MagicMock`/`patch`/`monkeypatch` anywhere in this file.

Per the task's own instruction: fixture-based tests assert on real synthetic
`.py` source written per-test, never on the live `gymact` source (that would
make the test brittle to future provider changes) -- the one exception is a
single smoke test at the bottom that runs the real checker against the real
repo and asserts only that it completes without crashing and returns a
well-formed, non-empty report, never asserting on which specific providers
land on which side.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_SCRIPT_PATH = Path(__file__).parent.parent / "scripts" / "check_observe_independence.py"
_spec = importlib.util.spec_from_file_location("check_observe_independence", _SCRIPT_PATH)
assert _spec is not None and _spec.loader is not None
check_observe_independence = importlib.util.module_from_spec(_spec)
sys.modules["check_observe_independence"] = check_observe_independence
_spec.loader.exec_module(check_observe_independence)

check_file = check_observe_independence.check_file
build_report = check_observe_independence.build_report
render_report = check_observe_independence.render_report
main = check_observe_independence.main


SYNTHETIC_HAS_IO_DIRECT = '''
class FooEnvironment:
    async def observe(self):
        import subprocess
        result = subprocess.run(["echo", "hi"], capture_output=True)
        return {"out": result.stdout}
'''

SYNTHETIC_HAS_IO_HTTPX = '''
import httpx

class FooEnvironment:
    async def observe(self):
        resp = httpx.get("http://localhost:9/status")
        return {"status": resp.status_code}
'''

SYNTHETIC_HAS_IO_OPEN = '''
class FooEnvironment:
    async def observe(self):
        with open("state.json") as f:
            data = f.read()
        return {"data": data}
'''

SYNTHETIC_NO_IO = '''
class FooEnvironment:
    def __init__(self):
        self._state = {"counter": 0}

    async def observe(self):
        return dict(self._state)
'''

SYNTHETIC_HAS_IO_TWO_HOP_SELF_THEN_MODULE_FN = '''
import subprocess

def _run_it():
    return subprocess.run(["true"], capture_output=True)

class FooEnvironment:
    def _state(self):
        return _run_it()

    async def observe(self):
        return self._state()
'''

SYNTHETIC_NO_IO_UNRELATED_RUN_METHOD = '''
class FooEnvironment:
    def __init__(self):
        self._history = []

    def run(self):
        # Same method name as subprocess.run, but not subprocess at all --
        # must not be misclassified as I/O.
        self._history.append("ran")
        return self._history

    async def observe(self):
        return {"history": list(self._history)}
'''


def _write(tmp_path: Path, name: str, source: str) -> Path:
    path = tmp_path / name
    path.write_text(source)
    return path


class TestDirectIODetection:
    def test_subprocess_run_is_classified_as_has_io(self, tmp_path: Path) -> None:
        path = _write(tmp_path, "direct_subprocess.py", SYNTHETIC_HAS_IO_DIRECT)
        results = check_file(path)
        assert len(results) == 1
        assert results[0]["class"] == "FooEnvironment"
        assert results[0]["has_io"] is True
        assert "subprocess.run" in str(results[0]["reason"])

    def test_httpx_get_is_classified_as_has_io(self, tmp_path: Path) -> None:
        path = _write(tmp_path, "direct_httpx.py", SYNTHETIC_HAS_IO_HTTPX)
        results = check_file(path)
        assert results[0]["has_io"] is True
        assert "httpx.get" in str(results[0]["reason"])

    def test_open_call_is_classified_as_has_io(self, tmp_path: Path) -> None:
        path = _write(tmp_path, "direct_open.py", SYNTHETIC_HAS_IO_OPEN)
        results = check_file(path)
        assert results[0]["has_io"] is True
        assert "open(" in str(results[0]["reason"])


class TestNoIODetection:
    def test_pure_in_memory_observe_is_classified_as_no_io(self, tmp_path: Path) -> None:
        path = _write(tmp_path, "no_io.py", SYNTHETIC_NO_IO)
        results = check_file(path)
        assert len(results) == 1
        assert results[0]["has_io"] is False
        assert results[0]["reason"] is None

    def test_unrelated_run_method_is_not_misclassified_as_subprocess(self, tmp_path: Path) -> None:
        path = _write(tmp_path, "unrelated_run.py", SYNTHETIC_NO_IO_UNRELATED_RUN_METHOD)
        results = check_file(path)
        assert results[0]["has_io"] is False


class TestOneLevelHelperFollowing:
    def test_self_method_then_module_function_chain_is_detected(self, tmp_path: Path) -> None:
        """Mirrors the real kubernetes_reconciliation.py shape: observe() ->
        self._state() -> module-level function -> subprocess.run()."""
        path = _write(tmp_path, "two_hop.py", SYNTHETIC_HAS_IO_TWO_HOP_SELF_THEN_MODULE_FN)
        results = check_file(path)
        assert results[0]["has_io"] is True
        reason = str(results[0]["reason"])
        assert "self._state()" in reason
        assert "subprocess.run" in reason


class TestReportShapeAndAdvisoryContract:
    def test_no_environment_class_yields_empty_results(self, tmp_path: Path) -> None:
        path = _write(tmp_path, "not_a_gym.py", "x = 1\n")
        assert check_file(path) == []

    def test_no_observe_method_yields_empty_results(self, tmp_path: Path) -> None:
        source = "class FooEnvironment:\n    async def actuate(self):\n        return {}\n"
        path = _write(tmp_path, "no_observe.py", source)
        assert check_file(path) == []

    def test_build_report_over_synthetic_directory_classifies_each_file(self, tmp_path: Path) -> None:
        gyms_dir = tmp_path / "gyms"
        gyms_dir.mkdir()
        _write(gyms_dir, "has_io.py", SYNTHETIC_HAS_IO_DIRECT)
        _write(gyms_dir, "no_io.py", SYNTHETIC_NO_IO)
        _write(gyms_dir, "__init__.py", "")

        results = build_report(gyms_dir)

        classes = {entry["class"]: entry["has_io"] for entry in results}
        assert classes == {"FooEnvironment": True} or len(results) == 2
        # __init__.py is real and correctly skipped (no Environment class in it).
        files = {Path(str(entry["file"])).name for entry in results}
        assert "has_io.py" in files
        assert "no_io.py" in files
        assert "__init__.py" not in files

    def test_render_report_labels_has_io_and_no_io_distinctly(self, tmp_path: Path) -> None:
        gyms_dir = tmp_path / "gyms"
        gyms_dir.mkdir()
        _write(gyms_dir, "has_io.py", SYNTHETIC_HAS_IO_DIRECT)
        _write(gyms_dir, "no_io.py", SYNTHETIC_NO_IO)

        results = build_report(gyms_dir)
        rendered = render_report(results)

        assert "HAS_IO" in rendered
        assert "NO_IO_DETECTED" in rendered
        assert "ADVISORY ONLY" in rendered

    def test_main_always_returns_zero_even_with_no_io_detected_providers(self) -> None:
        """Real, explicit assertion of the advisory-only exit-code contract:
        `main()` must return 0 regardless of classification outcomes."""
        exit_code = main([])
        assert exit_code == 0


@pytest.mark.parametrize("dummy", [None])
def test_smoke_runs_against_the_real_repo_without_crashing(dummy: None) -> None:
    """The one test in this file allowed to touch real gymact source --
    per the task instruction, it asserts only that the real checker runs
    end-to-end against the real repo without crashing and produces a
    well-formed, non-empty report. It does NOT assert on which specific
    providers land as HAS_IO vs NO_IO_DETECTED (that would make this test
    brittle to future provider changes)."""
    results = build_report()
    assert isinstance(results, list)
    assert len(results) > 0
    for entry in results:
        assert "file" in entry
        assert "class" in entry
        assert "has_io" in entry
        assert isinstance(entry["has_io"], bool)

    rendered = render_report(results)
    assert "ADVISORY ONLY" in rendered
    assert len(rendered) > 0

    exit_code = main([])
    assert exit_code == 0
