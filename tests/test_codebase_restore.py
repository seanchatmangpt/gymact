"""Chicago-style: real tests for `CodebaseEnvironment.checkpoint()`/
`restore()`'s one implemented dimension (`"filesystem"`, via real `git`
subprocess calls) and its explicit, typed refusal of every other dimension.

No mocking: every checkpoint/restore below runs against a real materialized
`CodebaseEnvironment` over a real temporary git worktree (the same
`CodebaseProvider` this whole gym uses), and asserts on real resulting file
contents and real `git rev-parse`/`git log` output -- never on "was
restore() called".
"""

from __future__ import annotations

from pathlib import Path

from gymact import AllowListAuthorityResolver, GymAct, MaterializationIntent
from gymact.gyms.codebase import CodebaseProvider
from gymact.models import ActuationIntent

AUTHORITY = "urn:test:codebase-restore-authority"
GIT_COMMIT = "urn:gymact:codebase:capability:git_commit"
APPLY_PATCH = "urn:gymact:codebase:capability:apply_patch"


def _authorized_gym() -> GymAct:
    gym = GymAct(authority_resolver=AllowListAuthorityResolver({AUTHORITY}))
    gym.register_provider(CodebaseProvider())
    return gym


async def test_checkpoint_records_a_real_head_sha() -> None:
    gym = _authorized_gym()
    materialization = await gym.materialize(
        MaterializationIntent(
            provider="codebase",
            config={"seed_files": {"a.txt": "one\n"}},
        )
    )
    episode_id = materialization.episode.episode_id
    env = gym._episodes[episode_id].environment
    try:
        await gym.act(
            ActuationIntent(
                episode_id=episode_id,
                capability=GIT_COMMIT,
                authority_ref=AUTHORITY,
                payload={"message": "first"},
            )
        )
        checkpoint = await env.checkpoint()
        real_head = (
            env._run_git(["rev-parse", "HEAD"]).stdout.strip()
        )
        assert checkpoint["head_sha"] == real_head
        assert len(checkpoint["head_sha"]) == 40
        assert checkpoint["source"] is None
        assert checkpoint["source_sha"] is None
    finally:
        await gym.teardown(episode_id, authority_ref=AUTHORITY)


async def test_restore_filesystem_dimension_really_reverts_a_real_file_via_git_reset(
) -> None:
    gym = _authorized_gym()
    materialization = await gym.materialize(
        MaterializationIntent(
            provider="codebase",
            config={"seed_files": {"a.txt": "one\n"}},
        )
    )
    episode_id = materialization.episode.episode_id
    env = gym._episodes[episode_id].environment
    try:
        commit_one = await gym.act(
            ActuationIntent(
                episode_id=episode_id,
                capability=GIT_COMMIT,
                authority_ref=AUTHORITY,
                payload={"message": "one"},
            )
        )
        assert commit_one.accepted is True
        checkpoint = await env.checkpoint()

        # Real mutation after the checkpoint: overwrite the file and commit
        # a second real revision.
        (env._worktree / "a.txt").write_text("two\n", encoding="utf-8")
        commit_two = await gym.act(
            ActuationIntent(
                episode_id=episode_id,
                capability=GIT_COMMIT,
                authority_ref=AUTHORITY,
                payload={"message": "two"},
            )
        )
        assert commit_two.accepted is True
        assert (env._worktree / "a.txt").read_text(encoding="utf-8") == "two\n"

        restore_receipt = await env.restore(checkpoint)
        assert restore_receipt["dimension"] == "filesystem"
        assert restore_receipt["method"] == "git_reset_hard"
        assert restore_receipt["reset_returncode"] == 0

        # Real resulting file content, not a narrated claim.
        assert (env._worktree / "a.txt").read_text(encoding="utf-8") == "one\n"
        real_head_after_restore = env._run_git(["rev-parse", "HEAD"]).stdout.strip()
        assert real_head_after_restore == checkpoint["head_sha"]
    finally:
        await gym.teardown(episode_id, authority_ref=AUTHORITY)


async def test_restore_filesystem_dimension_removes_real_untracked_files_too() -> None:
    gym = _authorized_gym()
    materialization = await gym.materialize(
        MaterializationIntent(
            provider="codebase",
            config={"seed_files": {"a.txt": "one\n"}},
        )
    )
    episode_id = materialization.episode.episode_id
    env = gym._episodes[episode_id].environment
    try:
        await gym.act(
            ActuationIntent(
                episode_id=episode_id,
                capability=GIT_COMMIT,
                authority_ref=AUTHORITY,
                payload={"message": "one"},
            )
        )
        checkpoint = await env.checkpoint()

        # A real untracked file appears after the checkpoint (never
        # committed) -- a real `git reset --hard` alone would NOT remove
        # this; the real `git clean -fdx` that follows it must.
        (env._worktree / "untracked.txt").write_text("stray\n", encoding="utf-8")
        assert (env._worktree / "untracked.txt").exists()

        await env.restore(checkpoint)

        assert not (env._worktree / "untracked.txt").exists()
        assert (env._worktree / "a.txt").read_text(encoding="utf-8") == "one\n"
    finally:
        await gym.teardown(episode_id, authority_ref=AUTHORITY)


async def test_restore_unsupported_dimension_raises_notimplementederror_not_silent_noop(
) -> None:
    gym = _authorized_gym()
    materialization = await gym.materialize(
        MaterializationIntent(
            provider="codebase",
            config={"seed_files": {"a.txt": "one\n"}},
        )
    )
    episode_id = materialization.episode.episode_id
    env = gym._episodes[episode_id].environment
    try:
        await gym.act(
            ActuationIntent(
                episode_id=episode_id,
                capability=GIT_COMMIT,
                authority_ref=AUTHORITY,
                payload={"message": "one"},
            )
        )
        checkpoint = await env.checkpoint()

        for unsupported in ("dependencies", "env_vars", "containers", "services"):
            raised = False
            try:
                await env.restore(checkpoint, dimensions=(unsupported,))
            except NotImplementedError as exc:
                raised = True
                assert unsupported in str(exc)
            assert raised is True, f"expected NotImplementedError for {unsupported!r}"
    finally:
        await gym.teardown(episode_id, authority_ref=AUTHORITY)


async def test_restore_unknown_dimension_name_is_a_clear_valueerror() -> None:
    gym = _authorized_gym()
    materialization = await gym.materialize(
        MaterializationIntent(
            provider="codebase",
            config={"seed_files": {"a.txt": "one\n"}},
        )
    )
    episode_id = materialization.episode.episode_id
    env = gym._episodes[episode_id].environment
    try:
        await gym.act(
            ActuationIntent(
                episode_id=episode_id,
                capability=GIT_COMMIT,
                authority_ref=AUTHORITY,
                payload={"message": "one"},
            )
        )
        checkpoint = await env.checkpoint()
        raised = False
        try:
            await env.restore(checkpoint, dimensions=("nonsense",))
        except ValueError as exc:
            raised = True
            assert "nonsense" in str(exc)
        assert raised is True
    finally:
        await gym.teardown(episode_id, authority_ref=AUTHORITY)


async def test_restore_via_the_default_single_arg_call_stays_filesystem_only() -> None:
    """The kernel calls `state.environment.restore(checkpoint)` with a
    single positional argument (`src/gymact/kernel.py`); this confirms that
    default call shape keeps working and resolves to the filesystem
    dimension without the caller ever needing to know about `dimensions`."""
    gym = _authorized_gym()
    materialization = await gym.materialize(
        MaterializationIntent(
            provider="codebase",
            config={"seed_files": {"a.txt": "one\n"}},
        )
    )
    episode_id = materialization.episode.episode_id
    env = gym._episodes[episode_id].environment
    try:
        await gym.act(
            ActuationIntent(
                episode_id=episode_id,
                capability=GIT_COMMIT,
                authority_ref=AUTHORITY,
                payload={"message": "one"},
            )
        )
        checkpoint = await env.checkpoint()
        (env._worktree / "a.txt").write_text("mutated\n", encoding="utf-8")

        result = await env.restore(checkpoint)  # single positional arg, like the kernel

        assert result["dimension"] == "filesystem"
        assert (env._worktree / "a.txt").read_text(encoding="utf-8") == "one\n"
    finally:
        await gym.teardown(episode_id, authority_ref=AUTHORITY)


async def test_kernel_restore_operation_really_reverts_real_file_state() -> None:
    """End-to-end through the real kernel `gym.restore()` port (not just
    `env.restore()` directly), mirroring how every other gym's restore is
    exercised in this suite (e.g. `tests/test_cloud_topology.py`)."""
    gym = _authorized_gym()
    materialization = await gym.materialize(
        MaterializationIntent(
            provider="codebase",
            config={"seed_files": {"a.txt": "one\n"}},
        )
    )
    episode_id = materialization.episode.episode_id
    env = gym._episodes[episode_id].environment
    try:
        await gym.act(
            ActuationIntent(
                episode_id=episode_id,
                capability=GIT_COMMIT,
                authority_ref=AUTHORITY,
                payload={"message": "one"},
            )
        )
        checkpoint = await env.checkpoint()
        (env._worktree / "a.txt").write_text("mutated\n", encoding="utf-8")
        await gym.act(
            ActuationIntent(
                episode_id=episode_id,
                capability=GIT_COMMIT,
                authority_ref=AUTHORITY,
                payload={"message": "mutated"},
            )
        )

        restore_result = await gym.restore(episode_id, checkpoint, authority_ref=AUTHORITY)
        assert restore_result.standing.value == "ALIVE"
        assert (env._worktree / "a.txt").read_text(encoding="utf-8") == "one\n"
    finally:
        await gym.teardown(episode_id, authority_ref=AUTHORITY)


async def test_restore_rebuilds_via_clone_at_ref_when_worktree_history_is_gone(
    tmp_path: Path,
) -> None:
    """The clone-at-ref rebuild fallback: an environment materialized from
    a real `clone_source`/`clone_sha` whose worktree is later wiped entirely
    (simulating a badly corrupted/destroyed environment -- no git repo left
    at that path at all) is restored by really re-running `clone_at_ref`
    against the original recorded source -- never a silent no-op."""
    import shutil
    import subprocess

    def _git(args: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", *args], cwd=cwd, capture_output=True, text=True, timeout=30.0, check=True
        )

    upstream = tmp_path / "upstream"
    upstream.mkdir()
    _git(["init"], cwd=upstream)
    _git(["config", "user.email", "restore-test@example.invalid"], cwd=upstream)
    _git(["config", "user.name", "restore test"], cwd=upstream)
    (upstream / "marker.txt").write_text("original\n", encoding="utf-8")
    _git(["add", "-A"], cwd=upstream)
    _git(["commit", "-m", "original"], cwd=upstream)
    upstream_sha = _git(["rev-parse", "HEAD"], cwd=upstream).stdout.strip()

    gym = _authorized_gym()
    materialization = await gym.materialize(
        MaterializationIntent(
            provider="codebase",
            config={"clone_source": str(upstream), "clone_sha": upstream_sha},
        )
    )
    episode_id = materialization.episode.episode_id
    env = gym._episodes[episode_id].environment
    try:
        checkpoint = await env.checkpoint()
        assert checkpoint["source"] == str(upstream)
        assert checkpoint["source_sha"] == upstream_sha

        # Real, severe corruption: wipe the entire worktree directory (no
        # git repo left there at all) -- the case restore()'s clone-at-ref
        # rebuild fallback exists for, since `git cat-file -e` in a
        # non-repo directory fails and the checkpointed commit is
        # therefore "not reachable" by definition.
        shutil.rmtree(env._worktree)
        env._worktree.mkdir(parents=True)

        restore_receipt = await env.restore(checkpoint)
        assert restore_receipt["method"] == "clone_at_ref_rebuild"
        assert restore_receipt["receipt"]["resolved_sha"] == upstream_sha
        assert (env._worktree / "marker.txt").read_text(encoding="utf-8") == "original\n"
    finally:
        # This environment's worktree came from clone_at_ref's "worktree"
        # strategy (upstream is a local git repo) -- deregister it cleanly.
        _git(["worktree", "remove", "--force", str(env._worktree)], cwd=upstream)
