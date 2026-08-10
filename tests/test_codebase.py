"""Chicago-style: a real GymAct episode driving `CodebaseProvider` over a
real, isolated temporary git repository -- not simulated, no mocking.

Every DO capability (`apply_patch`, `git_commit`, `run_test`, `run_build`)
is authority-gated per `CodebaseProvider.materialize()`'s
`requires_authority` default of `True`; every `act()` call below passes an
explicit `authority_ref` via a real `AllowListAuthorityResolver`, mirroring
`tests/test_multicloud.py`/`tests/test_terraform_docker_apply.py`.
"""

from __future__ import annotations

from gymact import AllowListAuthorityResolver, GymAct, MaterializationIntent
from gymact.gyms.codebase import CODEBASE_CAPABILITIES, CodebaseProvider
from gymact.models import ActuationIntent, Standing

AUTHORITY = "urn:test:codebase-authority"

INSPECT_TREE = "urn:gymact:codebase:capability:inspect_tree"
READ_FILE = "urn:gymact:codebase:capability:read_file"
INSPECT_MANIFEST = "urn:gymact:codebase:capability:inspect_manifest"
INSPECT_GIT_DIFF = "urn:gymact:codebase:capability:inspect_git_diff"
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
name = "codebase-gym-fixture"
version = "0.0.1"
"""


def _authorized_gym() -> GymAct:
    gym = GymAct(authority_resolver=AllowListAuthorityResolver({AUTHORITY}))
    gym.register_provider(CodebaseProvider())
    return gym


def _seed_config(*, requires_authority: bool = True) -> dict:
    return {
        "requires_authority": requires_authority,
        "seed_files": {
            "mymodule.py": _MODULE_SOURCE,
            "test_mymodule.py": _TEST_SOURCE,
            "pyproject.toml": _PYPROJECT,
        },
    }


async def test_materialize_creates_a_real_isolated_git_repo() -> None:
    gym = GymAct()
    gym.register_provider(CodebaseProvider())
    m = await gym.materialize(
        MaterializationIntent(provider="codebase", config=_seed_config(requires_authority=False))
    )
    assert m.accepted is True
    episode_id = m.episode.episode_id
    env = gym._episodes[episode_id].environment
    try:
        assert env.capabilities() == CODEBASE_CAPABILITIES
        observed = await env.observe()
        assert sorted(observed["tree"]) == ["mymodule.py", "pyproject.toml", "test_mymodule.py"]
        assert (env._worktree / ".git").is_dir()
    finally:
        await gym.teardown(episode_id)


async def test_inspect_tree_and_read_file_are_read_only() -> None:
    # READ capabilities are pure observation, never routed through gym.act
    # (the kernel refuses READ-typed capabilities via `act` with
    # `READ_CAPABILITY_IS_NOT_ACTUATION`, matching every other provider's
    # convention) -- exercised directly against the real environment,
    # mirroring `test_terraform_docker_apply.py`'s `plan` capability test.
    gym = GymAct()
    gym.register_provider(CodebaseProvider())
    m = await gym.materialize(
        MaterializationIntent(provider="codebase", config=_seed_config(requires_authority=False))
    )
    episode_id = m.episode.episode_id
    env = gym._episodes[episode_id].environment
    try:
        tree_capability = next(c for c in env.capabilities() if c.binding == "inspect_tree")
        tree_effect = await env.actuate(tree_capability, {})
        assert "mymodule.py" in tree_effect["after"]["tree"]

        read_capability = next(c for c in env.capabilities() if c.binding == "read_file")
        read_effect = await env.actuate(read_capability, {"path": "mymodule.py"})
        assert read_effect["after"]["content"] == _MODULE_SOURCE

        manifest_capability = next(c for c in env.capabilities() if c.binding == "inspect_manifest")
        manifest_effect = await env.actuate(manifest_capability, {})
        assert manifest_effect["after"]["manifest"] == "pyproject.toml"
        assert "codebase-gym-fixture" in manifest_effect["after"]["content"]
    finally:
        await gym.teardown(episode_id)


async def test_read_file_refuses_path_traversal_outside_worktree() -> None:
    gym = GymAct()
    gym.register_provider(CodebaseProvider())
    m = await gym.materialize(
        MaterializationIntent(provider="codebase", config=_seed_config(requires_authority=False))
    )
    episode_id = m.episode.episode_id
    env = gym._episodes[episode_id].environment
    try:
        capability = next(c for c in env.capabilities() if c.binding == "read_file")
        raised = False
        try:
            await env.actuate(capability, {"path": "../outside.txt"})
        except ValueError as exc:
            raised = True
            assert str(exc) == "AMBIGUOUS_SUBJECT_REFUSED"
        assert raised is True
    finally:
        await gym.teardown(episode_id)


async def test_run_test_executes_the_real_passing_pytest_suite() -> None:
    gym = _authorized_gym()
    m = await gym.materialize(
        MaterializationIntent(provider="codebase", config=_seed_config())
    )
    episode_id = m.episode.episode_id
    try:
        result = await gym.act(
            ActuationIntent(episode_id=episode_id, capability=RUN_TEST, authority_ref=AUTHORITY)
        )
        assert result.accepted is True
        assert result.effect["after"]["returncode"] == 0
        assert result.effect["after"]["passed"] is True
        assert "1 passed" in result.effect["after"]["stdout"]
    finally:
        await gym.teardown(episode_id, authority_ref=AUTHORITY)


async def test_run_build_py_compiles_the_real_source_files() -> None:
    gym = _authorized_gym()
    m = await gym.materialize(
        MaterializationIntent(provider="codebase", config=_seed_config())
    )
    episode_id = m.episode.episode_id
    try:
        result = await gym.act(
            ActuationIntent(episode_id=episode_id, capability=RUN_BUILD, authority_ref=AUTHORITY)
        )
        assert result.accepted is True
        assert result.effect["after"]["returncode"] == 0
        assert result.effect["after"]["built"] is True
        assert "mymodule.py" in result.effect["after"]["files_compiled"]
    finally:
        await gym.teardown(episode_id, authority_ref=AUTHORITY)


async def test_apply_patch_git_commit_and_diff_flow_mutates_real_files_and_history() -> None:
    gym = _authorized_gym()
    m = await gym.materialize(
        MaterializationIntent(provider="codebase", config=_seed_config())
    )
    episode_id = m.episode.episode_id
    env = gym._episodes[episode_id].environment
    try:
        # git diff only shows changes for tracked content, so commit the
        # seeded files first (real git_commit capability) before patching.
        seed_commit = await gym.act(
            ActuationIntent(
                episode_id=episode_id,
                capability=GIT_COMMIT,
                payload={"message": "seed files"},
                authority_ref=AUTHORITY,
            )
        )
        assert seed_commit.accepted is True

        patch_text = (
            "diff --git a/mymodule.py b/mymodule.py\n"
            "index 0000000..1111111 100644\n"
            "--- a/mymodule.py\n"
            "+++ b/mymodule.py\n"
            "@@ -1,2 +1,2 @@\n"
            " def add(a, b):\n"
            "-    return a + b\n"
            "+    return a + b  # patched\n"
        )
        patch_result = await gym.act(
            ActuationIntent(
                episode_id=episode_id,
                capability=APPLY_PATCH,
                payload={"patch": patch_text},
                authority_ref=AUTHORITY,
            )
        )
        assert patch_result.accepted is True
        assert patch_result.effect["after"]["applied"] is True
        assert patch_result.effect["after"]["returncode"] == 0

        # Real file mutation on disk.
        mutated_path = env._worktree / "mymodule.py"
        assert "# patched" in mutated_path.read_text(encoding="utf-8")

        diff_capability = next(c for c in env.capabilities() if c.binding == "inspect_git_diff")
        diff_effect = await env.actuate(diff_capability, {})
        assert "# patched" in diff_effect["after"]["diff"]

        commit_result = await gym.act(
            ActuationIntent(
                episode_id=episode_id,
                capability=GIT_COMMIT,
                payload={"message": "apply real patch"},
                authority_ref=AUTHORITY,
            )
        )
        assert commit_result.accepted is True
        assert commit_result.effect["after"]["committed"] is True
        sha = commit_result.effect["after"]["sha"]
        assert isinstance(sha, str) and len(sha) == 40

        # Real `git log` now shows the real commit.
        observed = await env.observe()
        assert "apply real patch" in observed["git_log"]
    finally:
        await gym.teardown(episode_id, authority_ref=AUTHORITY)


async def test_do_capabilities_are_refused_without_authority() -> None:
    gym = GymAct()  # DenyAuthorityResolver default
    gym.register_provider(CodebaseProvider())
    m = await gym.materialize(
        MaterializationIntent(provider="codebase", config=_seed_config())
    )
    episode_id = m.episode.episode_id
    try:
        result = await gym.act(
            ActuationIntent(episode_id=episode_id, capability=RUN_TEST)
        )
        assert result.accepted is False
        assert result.standing == Standing.REFUSED
    finally:
        await gym.teardown(episode_id)


async def test_materialize_requires_authority_defaults_true() -> None:
    provider = CodebaseProvider()
    env = await provider.materialize(scenario=None, config=_seed_config())
    try:
        assert env.requires_authority is True
    finally:
        await env.teardown()


async def test_teardown_removes_the_real_temporary_worktree() -> None:
    gym = GymAct()
    gym.register_provider(CodebaseProvider())
    m = await gym.materialize(
        MaterializationIntent(provider="codebase", config=_seed_config(requires_authority=False))
    )
    episode_id = m.episode.episode_id
    env = gym._episodes[episode_id].environment
    worktree = env._worktree
    assert worktree.is_dir()
    await gym.teardown(episode_id)
    assert not worktree.exists()
