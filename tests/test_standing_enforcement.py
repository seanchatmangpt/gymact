"""Chicago-style proof of `gymact.standing.require_standing`'s actual
contract, via real pytest subprocesses -- not by asserting against the
implementation's own internals, which would only prove it agrees with
itself.

Three real runs against one tiny scratch pytest file that claims a standing
which is never available:

1. no GYMACT_ALLOW_DEGRADED_STANDINGS set (the default) -> real subprocess
   FAILS. This is the headline behavior: an unavailable, undeclared
   standing is a hard failure, not a quiet skip.
2. GYMACT_ALLOW_DEGRADED_STANDINGS names the exact standing -> real
   subprocess SKIPS (exit 0).
3. GYMACT_ALLOW_DEGRADED_STANDINGS="*" -> same skip, proving the wildcard
   opt-out-of-strictness path.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

SCRATCH_TEST = """
from gymact.standing import require_standing


def test_claims_a_standing_that_is_never_available() -> None:
    require_standing(
        "FAKE:never-available",
        available=False,
        reason="this standing is never real; it exists only to prove the contract",
    )
    assert False, "require_standing should have failed or skipped before this ran"
"""


def _run_pytest(tmp_path: Path, *, env_overrides: dict[str, str]) -> subprocess.CompletedProcess:
    test_file = tmp_path / "test_scratch_standing.py"
    test_file.write_text(SCRATCH_TEST)

    env = dict(os.environ)
    env.pop("GYMACT_ALLOW_DEGRADED_STANDINGS", None)
    env.update(env_overrides)
    return subprocess.run(
        [sys.executable, "-m", "pytest", "-p", "no:cacheprovider", str(test_file)],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )


def test_unavailable_undeclared_standing_fails_the_real_subprocess(tmp_path) -> None:
    result = _run_pytest(tmp_path, env_overrides={})

    assert result.returncode != 0, result.stdout + result.stderr
    assert "FAKE:never-available" in result.stdout
    assert "GYMACT_ALLOW_DEGRADED_STANDINGS" in result.stdout


def test_explicitly_allowed_standing_skips_the_real_subprocess(tmp_path) -> None:
    result = _run_pytest(
        tmp_path,
        env_overrides={"GYMACT_ALLOW_DEGRADED_STANDINGS": "FAKE:never-available"},
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "skipped" in result.stdout.lower()


def test_wildcard_allow_also_skips_the_real_subprocess(tmp_path) -> None:
    result = _run_pytest(tmp_path, env_overrides={"GYMACT_ALLOW_DEGRADED_STANDINGS": "*"})

    assert result.returncode == 0, result.stdout + result.stderr
    assert "skipped" in result.stdout.lower()
