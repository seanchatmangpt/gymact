"""Crown test: one real, fresh-seeded, end-to-end CodebaseProvider episode
proving the full mission in a single run --

  architecture discovery -> real code modification -> real build/test
  execution -> independent verification -> durable OCEL -> replay from the
  original revision -> exact resulting revision identity (git SHA)

-- with standing reconstructed from durable OCEL evidence only, never from
a test-passed boolean treated as authoritative.

Phase A (this process, one `GymAct` + `CodebaseProvider` instance):
  1. Seed a fresh, isolated temp git repo (via `materialize(config=
     {"seed_files": ...})`) with a tiny real Python module carrying one
     deliberately injected, discoverable defect, and a real pytest test
     file that currently FAILS because of that defect -- a real regression
     oracle, not a fabricated one.
  2. `git_commit` (DO, authorized) the seeded, still-broken tree -- this is
     the real "before" revision SHA, taken verbatim from `git rev-parse`'s
     own stdout, not narrated.
  3. `inspect_tree` / `read_file` (READ, direct `env.actuate`, mirroring
     `test_terraform_docker_apply.py`'s `plan`-capability pattern -- the
     kernel's `act()` port refuses READ-typed capabilities) to discover the
     defect from the real file content.
  4. `run_test` (DO, authorized) confirms the real regression oracle really
     fails pre-fix (asserted on the real subprocess returncode/stdout).
  5. `apply_patch` (DO, authorized) with a real, correct unified diff fix.
  6. `run_test` (DO, authorized) confirms the fix really passes.
  7. `git_commit` (DO, authorized) the fixed tree -- the real "after"
     revision SHA.
  8. Export the real receipt trail to a durable OCEL 2.0 log via
     `gymact.ocel.receipts_to_ocel` / `validate_ocel_log` / `write_ocel_log`
     (same real pattern as `test_terraform_docker_apply.py`), persisted to
     disk *before* teardown deletes the worktree.

Phase B (independent replay, a genuinely separate OS process -- not just a
separate Python object): a `subprocess.run([sys.executable, "-c", ...])`
call that receives only two filesystem paths as argv (the persisted OCEL
log, and the still-live worktree path) and, in a fresh interpreter with no
imported `gymact.kernel`/`gymact.runtime`/`CodebaseEnvironment` instance and
no reference to any object from Phase A, independently:

  - loads the OCEL log from disk (`json.loads`, not the in-memory dict
    Phase A already built),
  - re-derives the real `git log` SHAs directly from the still-live repo,
  - reconstructs the exact `observe()`-shaped state dict from raw `git`
    subprocess calls (not by calling `CodebaseEnvironment.observe`), and
  - recomputes `gymact.evidence.digest` (BLAKE3 over RFC 8785 canonical
    JSON) over that independently reconstructed dict, confirming it equals
    the `post_state_digest` recorded on the OCEL log's final real `act`
    event for the "after" `git_commit`.

This ties the durable OCEL log's cryptographic evidence to the real git
revision identity without requiring the log to carry a bespoke "sha" field
that `receipts_to_ocel` does not (and per this repo's design should not)
fabricate -- the binding is the same BLAKE3/RFC8785 chain the kernel itself
uses to attest state, checked independently rather than trusted from the
original episode's own in-memory `effect` payloads.

Only after Phase B succeeds does this test call `teardown()`, deleting the
real worktree -- so Phase B's "real git history in the repo" claim is
checked against a worktree that has not yet been touched by cleanup.
"""

from __future__ import annotations

import difflib
import json
import subprocess
import sys
from pathlib import Path

from gymact import AllowListAuthorityResolver, GymAct, MaterializationIntent
from gymact.gyms.codebase import CodebaseProvider
from gymact.models import ActuationIntent, Operation
from gymact.ocel import receipts_to_ocel, validate_ocel_log, write_ocel_log
from gymact.process import ConformanceChecker

INSPECT_TREE = "urn:gymact:codebase:capability:inspect_tree"
READ_FILE = "urn:gymact:codebase:capability:read_file"
APPLY_PATCH = "urn:gymact:codebase:capability:apply_patch"
GIT_COMMIT = "urn:gymact:codebase:capability:git_commit"
RUN_TEST = "urn:gymact:codebase:capability:run_test"

AUTHORITY = "urn:test:codebase-crown-authority"

_BUGGY_CALC = (
    "def add_one(x):\n"
    "    return x - 1  # BUG: should add 1, subtracts instead\n"
)
_FIXED_CALC = (
    "def add_one(x):\n"
    "    return x + 1\n"
)
_TEST_CALC = (
    "from calc import add_one\n"
    "\n"
    "\n"
    "def test_add_one():\n"
    "    assert add_one(2) == 3\n"
)


def _unified_diff_patch(path: str, before: str, after: str) -> str:
    """Real unified diff (as `git apply` expects), built by `difflib` from
    the real before/after file contents -- not hand-typed line offsets that
    could silently drift out of sync with the fixture text above."""
    diff_lines = difflib.unified_diff(
        before.splitlines(keepends=True),
        after.splitlines(keepends=True),
        fromfile=f"a/{path}",
        tofile=f"b/{path}",
    )
    return "".join(diff_lines)


def _authorized_gym() -> GymAct:
    gym = GymAct(authority_resolver=AllowListAuthorityResolver({AUTHORITY}))
    gym.register_provider(CodebaseProvider())
    return gym


async def test_full_mission_codebase_episode_with_independent_ocel_replay(tmp_path) -> None:
    gym = _authorized_gym()
    receipts = []

    # --- materialize: fresh, isolated, real temp git repo, deliberately
    # seeded broken (a real regression oracle, not a fabricated one). ---
    materialization = await gym.materialize(
        MaterializationIntent(
            provider="codebase",
            config={
                "seed_files": {
                    "calc.py": _BUGGY_CALC,
                    "test_calc.py": _TEST_CALC,
                },
            },
        )
    )
    assert materialization.accepted is True
    receipts.append(materialization.receipt)
    episode_id = materialization.episode.episode_id
    env = gym._episodes[episode_id].environment
    worktree = env._worktree  # real Path, still alive until this test's teardown() call

    try:
        # --- "before" revision: commit the seeded (still-broken) tree. ---
        commit_before = await gym.act(
            ActuationIntent(
                episode_id=episode_id,
                capability=GIT_COMMIT,
                authority_ref=AUTHORITY,
                payload={"message": "seed: add_one() with an injected off-by-sign defect"},
            )
        )
        assert commit_before.accepted is True
        receipts.append(commit_before.receipt)
        before_sha = commit_before.effect["after"]["sha"]
        assert before_sha is not None and len(before_sha) == 40

        # Confirm directly against real git, not just the provider's own report.
        real_before_sha = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=worktree, capture_output=True, text=True, check=True
        ).stdout.strip()
        assert real_before_sha == before_sha

        # --- architecture discovery: real READ capabilities, direct
        # env.actuate (READ is refused at the kernel act() port -- matches
        # test_terraform_docker_apply.py's `plan` pattern). ---
        inspect_capability = next(
            c for c in env.capabilities() if c.binding == "inspect_tree"
        )
        tree_effect = await env.actuate(inspect_capability, {})
        assert "calc.py" in tree_effect["after"]["tree"]
        assert "test_calc.py" in tree_effect["after"]["tree"]

        read_capability = next(c for c in env.capabilities() if c.binding == "read_file")
        read_effect = await env.actuate(read_capability, {"path": "calc.py"})
        discovered_source = read_effect["after"]["content"]
        assert discovered_source == _BUGGY_CALC
        assert "x - 1" in discovered_source  # the real discovered defect

        # --- real regression oracle really fails pre-fix. ---
        test_before_fix = await gym.act(
            ActuationIntent(episode_id=episode_id, capability=RUN_TEST, authority_ref=AUTHORITY)
        )
        assert test_before_fix.accepted is True  # the *actuation* succeeded (real subprocess ran)
        receipts.append(test_before_fix.receipt)
        assert test_before_fix.effect["after"]["passed"] is False
        assert test_before_fix.effect["after"]["returncode"] != 0
        assert "1 failed" in test_before_fix.effect["after"]["stdout"]

        # --- real code modification: a real, correct unified-diff fix. ---
        patch_text = _unified_diff_patch("calc.py", _BUGGY_CALC, _FIXED_CALC)
        patch_result = await gym.act(
            ActuationIntent(
                episode_id=episode_id,
                capability=APPLY_PATCH,
                authority_ref=AUTHORITY,
                payload={"patch": patch_text},
            )
        )
        assert patch_result.accepted is True
        receipts.append(patch_result.receipt)
        assert patch_result.effect["after"]["applied"] is True
        assert (worktree / "calc.py").read_text(encoding="utf-8") == _FIXED_CALC

        # --- real build/test execution: the oracle now really passes. ---
        test_after_fix = await gym.act(
            ActuationIntent(episode_id=episode_id, capability=RUN_TEST, authority_ref=AUTHORITY)
        )
        assert test_after_fix.accepted is True
        receipts.append(test_after_fix.receipt)
        assert test_after_fix.effect["after"]["passed"] is True
        assert test_after_fix.effect["after"]["returncode"] == 0
        assert "1 passed" in test_after_fix.effect["after"]["stdout"]

        # --- "after" revision: commit the real fix. ---
        commit_after = await gym.act(
            ActuationIntent(
                episode_id=episode_id,
                capability=GIT_COMMIT,
                authority_ref=AUTHORITY,
                payload={"message": "fix: add_one() now adds 1"},
            )
        )
        assert commit_after.accepted is True
        receipts.append(commit_after.receipt)
        after_sha = commit_after.effect["after"]["sha"]
        assert after_sha is not None and len(after_sha) == 40
        assert after_sha != before_sha

        real_after_sha = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=worktree, capture_output=True, text=True, check=True
        ).stdout.strip()
        assert real_after_sha == after_sha

        real_git_log = subprocess.run(
            ["git", "log", "--format=%H", "--reverse"],
            cwd=worktree,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.split()
        assert real_git_log == [before_sha, after_sha]

        # --- conformance + durable OCEL export, BEFORE teardown deletes
        # the worktree, so Phase B below can independently check against
        # real, still-live git history. ---
        operations = [r.operation for r in receipts]
        assert operations == [
            Operation.MATERIALIZE,
            Operation.ACT,
            Operation.ACT,
            Operation.ACT,
            Operation.ACT,
            Operation.ACT,
        ]
        conformance = ConformanceChecker().check(operations)
        assert conformance.conformant is True

        log = receipts_to_ocel(receipts)
        validate_ocel_log(log)  # real jsonschema.validate against the real OCEL 2.0 schema

        log_path = tmp_path / "codebase-crown-episode.ocel.json"
        written_log, digest_hex = write_ocel_log(log_path, receipts)
        assert written_log == log
        assert log_path.is_file()
        assert len(digest_hex) == 64

        final_act_event = max(
            (e for e in log["events"] if e["type"] == Operation.ACT.value),
            key=lambda e: e["time"],
        )
        final_post_state_digest = next(
            a["value"] for a in final_act_event["attributes"] if a["name"] == "post_state_digest"
        )

        # --- Phase B: independent reconstruction in a genuinely separate
        # process, from disk only -- no shared Python object/module state
        # with Phase A above. ---
        reconstruction_script = r"""
import json
import subprocess
import sys
from pathlib import Path

from gymact.evidence import digest

log_path = Path(sys.argv[1])
worktree = Path(sys.argv[2])

log = json.loads(log_path.read_text())

def run_git(*args):
    return subprocess.run(
        ["git", *args], cwd=worktree, capture_output=True, text=True, check=True
    ).stdout

real_shas = run_git("log", "--format=%H", "--reverse").split()
assert len(real_shas) == 2, real_shas
real_before_sha, real_after_sha = real_shas

# Independently reconstruct the CodebaseEnvironment.observe()-shaped dict
# from raw git/filesystem calls -- not by importing CodebaseEnvironment.
tree = sorted(
    str(p.relative_to(worktree).as_posix())
    for p in worktree.rglob("*")
    if p.is_file() and ".git" not in p.parts
)
observed = {
    "worktree": str(worktree.resolve()),
    "tree": tree,
    "git_log": run_git("log", "--oneline").strip(),
    "git_status": run_git("status", "--porcelain").strip(),
}
recomputed_digest = digest(observed)

final_act_event = max(
    (e for e in log["events"] if e["type"] == "act"),
    key=lambda e: e["time"],
)
recorded_digest = next(
    a["value"] for a in final_act_event["attributes"] if a["name"] == "post_state_digest"
)

result = {
    "real_before_sha": real_before_sha,
    "real_after_sha": real_after_sha,
    "recomputed_digest": recomputed_digest,
    "recorded_digest": recorded_digest,
    "digest_match": recomputed_digest == recorded_digest,
    "n_act_events": sum(1 for e in log["events"] if e["type"] == "act"),
}
print(json.dumps(result))
"""
        subprocess_result = subprocess.run(
            [sys.executable, "-c", reconstruction_script, str(log_path), str(worktree)],
            capture_output=True,
            text=True,
            timeout=60.0,
        )
        assert subprocess_result.returncode == 0, (
            f"independent reconstruction subprocess failed:\n"
            f"stdout={subprocess_result.stdout}\nstderr={subprocess_result.stderr}"
        )
        reconstructed = json.loads(subprocess_result.stdout.strip().splitlines()[-1])

        # The independently-reconstructed real git SHAs match the ones
        # captured live during the episode...
        assert reconstructed["real_before_sha"] == before_sha
        assert reconstructed["real_after_sha"] == after_sha
        # ...and the independently recomputed BLAKE3/RFC8785 state digest
        # (built with zero gymact runtime/environment objects, only raw
        # git + the public digest() function, in a fresh interpreter) ties
        # that real git revision identity to the durable OCEL log's own
        # recorded evidence -- not to anything held in Phase A's memory.
        assert reconstructed["recorded_digest"] == final_post_state_digest
        assert reconstructed["digest_match"] is True
        assert reconstructed["n_act_events"] == 5

    finally:
        teardown_receipt = await gym.teardown(episode_id, authority_ref=AUTHORITY)
        receipts.append(teardown_receipt)
        assert not worktree.exists()  # real deletion, confirmed on the real filesystem
