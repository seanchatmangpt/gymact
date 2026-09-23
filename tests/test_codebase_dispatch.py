"""Chicago-style: real per-`ProjectKind` `run_build`/`run_test` dispatch,
exercised end to end through the real `CodebaseProvider`/`CodebaseEnvironment`
-- not just the abstract `_build_commands_for`/`_test_commands_for` helpers
in isolation.

Every fixture below is seeded via `config.seed_files` into a real, isolated
temporary git worktree (the same primitive `tests/test_codebase.py` already
exercises), then a real `cargo build`/`cargo test`, `mix compile`/`mix test`,
`npm install`+`npm run build`/`npm test`, or `go build`/`go test` subprocess
is actually run against it via the real `run_build`/`run_test` capabilities
-- real toolchains, real exit codes, never mocked or fabricated. A test
skips (named, visible -- never silently substituted) only when the real
toolchain binary genuinely is not on this machine's PATH.
"""

from __future__ import annotations

import shutil

import pytest

from gymact import AllowListAuthorityResolver, GymAct, MaterializationIntent
from gymact.gyms.codebase import CodebaseProvider
from gymact.models import ActuationIntent

AUTHORITY = "urn:test:codebase-dispatch-authority"
RUN_BUILD = "urn:gymact:codebase:capability:run_build"
RUN_TEST = "urn:gymact:codebase:capability:run_test"

_CARGO_TOML = """\
[package]
name = "fixture"
version = "0.1.0"
edition = "2021"

[[bin]]
name = "fixture"
path = "src/main.rs"
"""

_MAIN_RS = """\
fn add(a: i32, b: i32) -> i32 {
    a + b
}

fn main() {
    println!("{}", add(2, 3));
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_add() {
        assert_eq!(add(2, 3), 5);
    }
}
"""

_MIX_EXS = """\
defmodule FixtureApp.MixProject do
  use Mix.Project

  def project do
    [
      app: :fixture_app,
      version: "0.1.0",
      elixir: "~> 1.14",
      start_permanent: Mix.env() == :prod,
      deps: []
    ]
  end

  def application do
    [extra_applications: [:logger]]
  end
end
"""

_FIXTURE_APP_EX = """\
defmodule FixtureApp do
  def add(a, b) do
    a + b
  end
end
"""

_FIXTURE_APP_TEST_EXS = """\
defmodule FixtureAppTest do
  use ExUnit.Case

  test "add/2" do
    assert FixtureApp.add(2, 3) == 5
  end
end
"""

_TEST_HELPER_EXS = "ExUnit.start()\n"

_PACKAGE_JSON = """\
{
  "name": "fixture-app",
  "version": "1.0.0",
  "private": true,
  "scripts": {
    "build": "node -e \\"console.log('build ok')\\"",
    "test": "node --test"
  }
}
"""

_INDEX_JS = """\
function add(a, b) {
  return a + b;
}
module.exports = { add };
"""

_BASIC_TEST_JS = """\
const test = require('node:test');
const assert = require('node:assert');
const { add } = require('../index.js');

test('add works', () => {
  assert.strictEqual(add(2, 3), 5);
});
"""

_GO_MOD = "module fixture\n\ngo 1.21\n"

_MAIN_GO = """\
package main

import "fmt"

func add(a, b int) int {
	return a + b
}

func main() {
	fmt.Println(add(2, 3))
}
"""

_MAIN_TEST_GO = """\
package main

import "testing"

func TestAdd(t *testing.T) {
	if add(2, 3) != 5 {
		t.Fatalf("expected 5")
	}
}
"""


def _authorized_gym() -> GymAct:
    gym = GymAct(authority_resolver=AllowListAuthorityResolver({AUTHORITY}))
    gym.register_provider(CodebaseProvider())
    return gym


async def _materialize(gym: GymAct, seed_files: dict[str, str]) -> str:
    materialization = await gym.materialize(
        MaterializationIntent(
            provider="codebase",
            config={"requires_authority": True, "seed_files": seed_files},
        )
    )
    assert materialization.accepted is True
    return materialization.episode.episode_id


@pytest.mark.skipif(shutil.which("cargo") is None, reason="cargo not on PATH")
async def test_run_build_dispatches_real_cargo_build() -> None:
    gym = _authorized_gym()
    episode_id = await _materialize(
        gym, {"Cargo.toml": _CARGO_TOML, "src/main.rs": _MAIN_RS}
    )
    try:
        result = await gym.act(
            ActuationIntent(episode_id=episode_id, capability=RUN_BUILD, authority_ref=AUTHORITY)
        )
        assert result.accepted is True, result.reason
        after = result.effect["after"]
        assert after["project_kind"] == "rust"
        assert after["returncode"] == 0
        assert after["built"] is True
        assert after["steps"][0]["command"] == ["cargo", "build"]
    finally:
        await gym.teardown(episode_id, authority_ref=AUTHORITY)


@pytest.mark.skipif(shutil.which("cargo") is None, reason="cargo not on PATH")
async def test_run_test_dispatches_real_cargo_test() -> None:
    gym = _authorized_gym()
    episode_id = await _materialize(
        gym, {"Cargo.toml": _CARGO_TOML, "src/main.rs": _MAIN_RS}
    )
    try:
        result = await gym.act(
            ActuationIntent(episode_id=episode_id, capability=RUN_TEST, authority_ref=AUTHORITY)
        )
        assert result.accepted is True, result.reason
        after = result.effect["after"]
        assert after["project_kind"] == "rust"
        assert after["returncode"] == 0
        assert after["passed"] is True
        assert "test result: ok" in after["stdout"]
    finally:
        await gym.teardown(episode_id, authority_ref=AUTHORITY)


@pytest.mark.skipif(shutil.which("cargo") is None, reason="cargo not on PATH")
async def test_run_test_dispatches_real_cargo_test_and_really_fails_on_a_real_bug() -> None:
    broken_main_rs = _MAIN_RS.replace("a + b", "a - b", 1)
    gym = _authorized_gym()
    episode_id = await _materialize(
        gym, {"Cargo.toml": _CARGO_TOML, "src/main.rs": broken_main_rs}
    )
    try:
        result = await gym.act(
            ActuationIntent(episode_id=episode_id, capability=RUN_TEST, authority_ref=AUTHORITY)
        )
        assert result.accepted is True  # actuation succeeded; the *test run* failed
        after = result.effect["after"]
        assert after["returncode"] != 0
        assert after["passed"] is False
        assert "FAILED" in after["stdout"] or "test result: FAILED" in after["stdout"]
    finally:
        await gym.teardown(episode_id, authority_ref=AUTHORITY)


@pytest.mark.skipif(shutil.which("mix") is None, reason="mix not on PATH")
async def test_run_build_dispatches_real_mix_compile() -> None:
    gym = _authorized_gym()
    episode_id = await _materialize(
        gym,
        {
            "mix.exs": _MIX_EXS,
            "lib/fixture_app.ex": _FIXTURE_APP_EX,
            "test/fixture_app_test.exs": _FIXTURE_APP_TEST_EXS,
            "test/test_helper.exs": _TEST_HELPER_EXS,
        },
    )
    try:
        result = await gym.act(
            ActuationIntent(episode_id=episode_id, capability=RUN_BUILD, authority_ref=AUTHORITY)
        )
        assert result.accepted is True, result.reason
        after = result.effect["after"]
        assert after["project_kind"] == "elixir"
        assert after["returncode"] == 0
        assert after["built"] is True
        assert after["steps"][-1]["command"] == ["mix", "compile"]
    finally:
        await gym.teardown(episode_id, authority_ref=AUTHORITY)


@pytest.mark.skipif(shutil.which("mix") is None, reason="mix not on PATH")
async def test_run_test_dispatches_real_mix_test() -> None:
    gym = _authorized_gym()
    episode_id = await _materialize(
        gym,
        {
            "mix.exs": _MIX_EXS,
            "lib/fixture_app.ex": _FIXTURE_APP_EX,
            "test/fixture_app_test.exs": _FIXTURE_APP_TEST_EXS,
            "test/test_helper.exs": _TEST_HELPER_EXS,
        },
    )
    try:
        result = await gym.act(
            ActuationIntent(episode_id=episode_id, capability=RUN_TEST, authority_ref=AUTHORITY)
        )
        assert result.accepted is True, result.reason
        after = result.effect["after"]
        assert after["project_kind"] == "elixir"
        assert after["returncode"] == 0
        assert after["passed"] is True
        assert "1 test, 0 failures" in after["stdout"]
    finally:
        await gym.teardown(episode_id, authority_ref=AUTHORITY)


@pytest.mark.skipif(shutil.which("node") is None, reason="node not on PATH")
@pytest.mark.skipif(shutil.which("npm") is None, reason="npm not on PATH")
async def test_run_build_dispatches_real_npm_install_and_build_script() -> None:
    gym = _authorized_gym()
    episode_id = await _materialize(
        gym,
        {
            "package.json": _PACKAGE_JSON,
            "index.js": _INDEX_JS,
            "test/basic.test.js": _BASIC_TEST_JS,
        },
    )
    try:
        result = await gym.act(
            ActuationIntent(episode_id=episode_id, capability=RUN_BUILD, authority_ref=AUTHORITY)
        )
        assert result.accepted is True, result.reason
        after = result.effect["after"]
        assert after["project_kind"] == "node"
        assert after["returncode"] == 0
        assert after["built"] is True
        # install, then the declared "build" script -- both real steps ran.
        assert [step["command"][1] for step in after["steps"]] == ["install", "run"]
        assert "build ok" in after["stdout"]
    finally:
        await gym.teardown(episode_id, authority_ref=AUTHORITY)


@pytest.mark.skipif(shutil.which("node") is None, reason="node not on PATH")
@pytest.mark.skipif(shutil.which("npm") is None, reason="npm not on PATH")
async def test_run_test_dispatches_real_npm_install_and_node_test_runner() -> None:
    gym = _authorized_gym()
    episode_id = await _materialize(
        gym,
        {
            "package.json": _PACKAGE_JSON,
            "index.js": _INDEX_JS,
            "test/basic.test.js": _BASIC_TEST_JS,
        },
    )
    try:
        result = await gym.act(
            ActuationIntent(episode_id=episode_id, capability=RUN_TEST, authority_ref=AUTHORITY)
        )
        assert result.accepted is True, result.reason
        after = result.effect["after"]
        assert after["project_kind"] == "node"
        assert after["returncode"] == 0
        assert after["passed"] is True
        assert "pass 1" in after["stdout"] or "# pass 1" in after["stdout"]
    finally:
        await gym.teardown(episode_id, authority_ref=AUTHORITY)


@pytest.mark.skipif(shutil.which("go") is None, reason="go not on PATH")
async def test_run_build_dispatches_real_go_build() -> None:
    gym = _authorized_gym()
    episode_id = await _materialize(gym, {"go.mod": _GO_MOD, "main.go": _MAIN_GO})
    try:
        result = await gym.act(
            ActuationIntent(episode_id=episode_id, capability=RUN_BUILD, authority_ref=AUTHORITY)
        )
        assert result.accepted is True, result.reason
        after = result.effect["after"]
        assert after["project_kind"] == "go"
        assert after["returncode"] == 0
        assert after["built"] is True
        assert after["steps"][0]["command"] == ["go", "build", "./..."]
    finally:
        await gym.teardown(episode_id, authority_ref=AUTHORITY)


@pytest.mark.skipif(shutil.which("go") is None, reason="go not on PATH")
async def test_run_test_dispatches_real_go_test() -> None:
    gym = _authorized_gym()
    episode_id = await _materialize(
        gym, {"go.mod": _GO_MOD, "main.go": _MAIN_GO, "main_test.go": _MAIN_TEST_GO}
    )
    try:
        result = await gym.act(
            ActuationIntent(episode_id=episode_id, capability=RUN_TEST, authority_ref=AUTHORITY)
        )
        assert result.accepted is True, result.reason
        after = result.effect["after"]
        assert after["project_kind"] == "go"
        assert after["returncode"] == 0
        assert after["passed"] is True
        assert "ok" in after["stdout"]
    finally:
        await gym.teardown(episode_id, authority_ref=AUTHORITY)


async def test_mixed_project_kind_is_refused_not_guessed() -> None:
    # Direct env.actuate(), mirroring test_codebase.py's
    # test_read_file_refuses_path_traversal_outside_worktree -- the kernel's
    # own act() port collapses every provider exception's message down to
    # "PROVIDER_ERROR:<ExceptionType>" in its Receipt.reason, so the real
    # refusal message is only observable by calling the environment
    # directly, same as that existing test does for AMBIGUOUS_SUBJECT_REFUSED.
    gym = _authorized_gym()
    episode_id = await _materialize(
        gym,
        {
            "Cargo.toml": _CARGO_TOML,
            "src/main.rs": _MAIN_RS,
            "pyproject.toml": '[project]\nname = "wrapper"\n',
        },
    )
    env = gym._episodes[episode_id].environment
    try:
        build_capability = next(c for c in env.capabilities() if c.binding == "run_build")
        raised = False
        try:
            await env.actuate(build_capability, {})
        except ValueError as exc:
            raised = True
            assert "PROJECT_KIND_MIXED_AMBIGUOUS_REFUSED" in str(exc)
        assert raised is True
    finally:
        await gym.teardown(episode_id, authority_ref=AUTHORITY)


async def test_mixed_project_kind_dispatch_can_be_disambiguated_via_payload_kind() -> None:
    if shutil.which("cargo") is None:
        pytest.skip("cargo not on PATH")
    gym = _authorized_gym()
    episode_id = await _materialize(
        gym,
        {
            "Cargo.toml": _CARGO_TOML,
            "src/main.rs": _MAIN_RS,
            "pyproject.toml": '[project]\nname = "wrapper"\n',
        },
    )
    try:
        result = await gym.act(
            ActuationIntent(
                episode_id=episode_id,
                capability=RUN_BUILD,
                authority_ref=AUTHORITY,
                payload={"kind": "rust"},
            )
        )
        assert result.accepted is True, result.reason
        assert result.effect["after"]["project_kind"] == "rust"
        assert result.effect["after"]["built"] is True
    finally:
        await gym.teardown(episode_id, authority_ref=AUTHORITY)


async def test_unknown_project_kind_without_python_files_is_refused() -> None:
    gym = _authorized_gym()
    episode_id = await _materialize(gym, {"README.md": "# nothing recognizable\n"})
    env = gym._episodes[episode_id].environment
    try:
        test_capability = next(c for c in env.capabilities() if c.binding == "run_test")
        raised = False
        try:
            await env.actuate(test_capability, {})
        except ValueError as exc:
            raised = True
            assert "PROJECT_KIND_UNKNOWN_REFUSED" in str(exc)
        assert raised is True
    finally:
        await gym.teardown(episode_id, authority_ref=AUTHORITY)
