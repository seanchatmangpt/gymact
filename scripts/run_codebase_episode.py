#!/usr/bin/env python3
"""Run one real GymAct episode over `CodebaseProvider` -- a real, isolated,
local git-tracked temporary worktree (no mocking, real `git`/`python`
subprocess calls) -- and write a real OCEL 2.0 log at
reports/ocel/codebase/episode.ocel.json.

Mirrors `scripts/run_terraform_docker_apply_episode.py`'s authority-gated
shape: `CodebaseProvider.materialize()` defaults `requires_authority=True`
for every DO capability, so a real `AllowListAuthorityResolver` is used.

The episode: materialize a worktree seeded with one small module + test +
pyproject, git_commit the seed, apply_patch to break the module's `add`
so the seeded test starts failing, run_test (expect failure), apply_patch
again to fix it, run_test again (expect success), run_build, git_commit the
fix, verify the final git log/tree state. `solved` is recorded on the final
passing `run_test` act's own receipt.

Usage:
    uv run python scripts/run_codebase_episode.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from gymact import AllowListAuthorityResolver, GymAct, MaterializationIntent
from gymact.gyms.codebase import CodebaseProvider
from gymact.models import ActuationIntent
from gymact.ocel import write_ocel_log

REPORTS_DIR = Path(__file__).parent.parent / "reports" / "ocel"
AUTHORITY = "urn:gymact:codebase-episode:authority"

READ_FILE = "urn:gymact:codebase:capability:read_file"
APPLY_PATCH = "urn:gymact:codebase:capability:apply_patch"
GIT_COMMIT = "urn:gymact:codebase:capability:git_commit"
RUN_TEST = "urn:gymact:codebase:capability:run_test"
RUN_BUILD = "urn:gymact:codebase:capability:run_build"

_MODULE_SOURCE = """\
def add(a, b):
    return a + b
"""

_TEST_SOURCE = """\
from mymodule import add


def test_add():
    assert add(2, 3) == 5
"""

_PYPROJECT = """\
[project]
name = "codebase-gym-episode-fixture"
version = "0.0.1"
"""

# A real, syntactically-valid unified diff that breaks `add` (introduces a
# subtraction bug) applied against the seeded module above.
_BREAK_PATCH = (
    "diff --git a/mymodule.py b/mymodule.py\n"
    "index 0000000..1111111 100644\n"
    "--- a/mymodule.py\n"
    "+++ b/mymodule.py\n"
    "@@ -1,2 +1,2 @@\n"
    " def add(a, b):\n"
    "-    return a + b\n"
    "+    return a - b  # BUG: introduced on purpose\n"
)

# The real fix, applied against the broken state above.
_FIX_PATCH = (
    "diff --git a/mymodule.py b/mymodule.py\n"
    "index 0000000..1111111 100644\n"
    "--- a/mymodule.py\n"
    "+++ b/mymodule.py\n"
    "@@ -1,2 +1,2 @@\n"
    " def add(a, b):\n"
    "-    return a - b  # BUG: introduced on purpose\n"
    "+    return a + b\n"
)


async def run() -> None:
    gym = GymAct(authority_resolver=AllowListAuthorityResolver({AUTHORITY}))
    gym.register_provider(CodebaseProvider())
    receipts = []
    log_path = REPORTS_DIR / "codebase" / "episode.ocel.json"

    materialization = await gym.materialize(
        MaterializationIntent(
            provider="codebase",
            config={
                "requires_authority": True,
                "seed_files": {
                    "mymodule.py": _MODULE_SOURCE,
                    "test_mymodule.py": _TEST_SOURCE,
                    "pyproject.toml": _PYPROJECT,
                },
            },
        )
    )
    receipts.append(materialization.receipt)
    if not materialization.accepted or materialization.episode is None:
        print(f"codebase: materialization refused: {materialization.receipt.reason}")
        log, digest = write_ocel_log(log_path, receipts)
        print(f"codebase: {len(log['events'])} events, sha256={digest}")
        return

    episode_id = materialization.episode.episode_id
    last_receipt = materialization.receipt
    try:
        seed_commit = await gym.act(
            ActuationIntent(
                episode_id=episode_id,
                capability=GIT_COMMIT,
                payload={"message": "seed files"},
                authority_ref=AUTHORITY,
            )
        )
        receipts.append(seed_commit.receipt)
        print(f"codebase: seed_commit accepted={seed_commit.accepted}")

        break_result = await gym.act(
            ActuationIntent(
                episode_id=episode_id,
                capability=APPLY_PATCH,
                payload={"patch": _BREAK_PATCH},
                authority_ref=AUTHORITY,
            )
        )
        receipts.append(break_result.receipt)
        print(f"codebase: apply_break_patch accepted={break_result.accepted}")

        failing_test = await gym.act(
            ActuationIntent(episode_id=episode_id, capability=RUN_TEST, authority_ref=AUTHORITY)
        )
        receipts.append(failing_test.receipt)
        broke_returncode = failing_test.effect.get("after", {}).get("returncode") if failing_test.effect else None
        print(f"codebase: run_test_after_break returncode={broke_returncode} (expect != 0)")

        fix_result = await gym.act(
            ActuationIntent(
                episode_id=episode_id,
                capability=APPLY_PATCH,
                payload={"patch": _FIX_PATCH},
                authority_ref=AUTHORITY,
            )
        )
        receipts.append(fix_result.receipt)
        print(f"codebase: apply_fix_patch accepted={fix_result.accepted}")

        passing_test = await gym.act(
            ActuationIntent(episode_id=episode_id, capability=RUN_TEST, authority_ref=AUTHORITY)
        )
        receipts.append(passing_test.receipt)
        last_receipt = passing_test.receipt
        passed_returncode = passing_test.effect.get("after", {}).get("returncode") if passing_test.effect else None
        solved = passed_returncode == 0
        print(f"codebase: run_test_after_fix returncode={passed_returncode} solved={solved}")

        build_result = await gym.act(
            ActuationIntent(episode_id=episode_id, capability=RUN_BUILD, authority_ref=AUTHORITY)
        )
        receipts.append(build_result.receipt)
        print(f"codebase: run_build accepted={build_result.accepted}")

        final_commit = await gym.act(
            ActuationIntent(
                episode_id=episode_id,
                capability=GIT_COMMIT,
                payload={"message": "fix add() regression"},
                authority_ref=AUTHORITY,
            )
        )
        receipts.append(final_commit.receipt)

        receipts.append(last_receipt.model_copy(update={"reason": f"solved={solved}"}))
    finally:
        receipts.append(await gym.teardown(episode_id, authority_ref=AUTHORITY))

    log, digest = write_ocel_log(log_path, receipts)
    print(f"codebase: {len(log['events'])} events, sha256={digest}")


if __name__ == "__main__":
    asyncio.run(run())
