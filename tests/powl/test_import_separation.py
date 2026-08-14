# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Anti-self-attestation: the validator must not pull in the executor.

A structural validator that shares a code path with the machinery producing or
interpreting the model attests to its own output. These tests enforce the
separation in a **fresh subprocess** -- checking ``sys.modules`` inside the
already-loaded pytest process would be meaningless, because another test
module may have imported the executor first.

A meta-path blocker turns a forbidden import into an immediate hard failure
rather than a post-hoc ``sys.modules`` inspection, so an import buried inside a
function body is caught too, as long as it runs.

This is the gymact-local counterpart of the sibling autofde-lab repo's test
of the same name (``autofde-lab/tests/powl/test_import_separation.py``),
which enforces the identical invariant for ``autofde_lab.powl.validate``.
That test cannot cover this package: it runs in a different repo, against a
different installed distribution, and gymact's own CI never executes it.
``src/gymact/powl/validate.py``'s docstring names *this* file, in *this*
tree, as the enforcement mechanism -- so it must actually exist here.
"""

from __future__ import annotations

import json
import subprocess
import sys

import pytest

_FORBIDDEN = ("gymact.powl.executor", "gymact.powl.semantics")

_PROBE = """
import importlib, importlib.util, json, sys

FORBIDDEN = {forbidden!r}

class _Blocker:
    def find_spec(self, name, path=None, target=None):
        if name in FORBIDDEN:
            raise AssertionError("FORBIDDEN_IMPORT:" + name)
        return None

sys.meta_path.insert(0, _Blocker())
importlib.import_module({module!r})
print(json.dumps(sorted(m for m in sys.modules if m.startswith("gymact.powl"))))
"""


def _loaded_powl_modules(module: str) -> list[str]:
    proc = subprocess.run(
        [sys.executable, "-c", _PROBE.format(module=module, forbidden=_FORBIDDEN)],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        pytest.fail(f"importing {module} in isolation failed:\n{proc.stderr}")
    return json.loads(proc.stdout.strip().splitlines()[-1])


def _module_exists(module: str) -> bool:
    proc = subprocess.run(
        [
            sys.executable,
            "-c",
            f"import importlib.util as u; raise SystemExit(0 if u.find_spec({module!r}) else 1)",
        ],
        capture_output=True,
        text=True,
    )
    return proc.returncode == 0


def _assert_separated(module: str) -> None:
    loaded = _loaded_powl_modules(module)
    assert module in loaded
    for forbidden in _FORBIDDEN:
        assert forbidden not in loaded, (
            f"{forbidden} was pulled in by importing {module}; loaded={loaded}"
        )


def test_validate_does_not_import_executor_or_semantics():
    _assert_separated("gymact.powl.validate")


def test_probe_would_catch_a_violation():
    """The probe is falsifiable: a module that *does* import the executor fails it."""
    proc = subprocess.run(
        [sys.executable, "-c", _PROBE.format(module="gymact.powl.executor", forbidden=_FORBIDDEN)],
        capture_output=True,
        text=True,
    )
    assert proc.returncode != 0
    assert "FORBIDDEN_IMPORT:gymact.powl.executor" in proc.stderr
