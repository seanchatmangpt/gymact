"""Chicago-style tests for `gymact.gyms.chatman_state_gym` -- a real
`ChatmanStateEnvironment`/`ChatmanStateProvider` lifecycle against this
actual machine and this actual, already-authenticated `gh` session. No
`unittest.mock` / `Mock` / `MagicMock` / `patch` / `monkeypatch` anywhere in
this file.

GENERATED-CAPABILITY-CATALOG note: `CHATMAN_STATE_CAPABILITIES` itself is
ggen-generated from `ggen/chatman-state-pack/ontology.ttl`; this test file
is hand-written (unlike `test_k8s_resource_gym.py`), asserting against that
generated catalog's real, current shape.
"""

from __future__ import annotations

import asyncio
import shutil

import pytest

from gymact.gyms.chatman_state_gym import (
    CHATMAN_STATE_CAPABILITIES,
    ChatmanStateEnvironment,
    ChatmanStateProvider,
    _CAPABILITY_BY_BINDING,
)

pytestmark = pytest.mark.skipif(
    shutil.which("gh") is None or shutil.which("git") is None,
    reason="real gh/git CLI required on PATH",
)


def test_capability_catalog_covers_every_real_binding() -> None:
    bindings = {c.binding for c in CHATMAN_STATE_CAPABILITIES}
    assert bindings == {
        "list_local_repos",
        "list_github_repos",
        "estimated_effort_cost",
        "portfolio_summary",
    }
    for capability in CHATMAN_STATE_CAPABILITIES:
        assert capability.iri.startswith("urn:gymact:chatman-state:capability:")


def test_real_provider_materialize_observe_actuate_verify_checkpoint_restore_teardown() -> None:
    async def run() -> None:
        provider = ChatmanStateProvider()
        env = await provider.materialize(scenario=None, config={"repo_limit": 5})
        assert isinstance(env, ChatmanStateEnvironment)

        observed = await env.observe()
        assert observed["repo_limit"] == 5

        local = _CAPABILITY_BY_BINDING["list_local_repos"]
        result = await env.actuate(local, {})
        assert len(result["result"]) <= 5
        assert all("name" in row and "path" in row for row in result["result"])

        github = _CAPABILITY_BY_BINDING["list_github_repos"]
        result2 = await env.actuate(github, {})
        assert len(result2["result"]) <= 5
        assert all("name" in row and "pushed_at" in row for row in result2["result"])

        summary = _CAPABILITY_BY_BINDING["portfolio_summary"]
        result3 = await env.actuate(summary, {})
        assert result3["result"]["local_repo_count_found"] >= result3["result"]["local_repo_count_returned"]
        assert result3["result"]["github_repo_count_found"] >= result3["result"]["github_repo_count_returned"]

        passed, verified = await env.verify({"repo_limit": 5})
        assert passed is True
        assert verified["repo_limit"] == 5

        checkpoint = await env.checkpoint()
        await env.restore(checkpoint)

        await env.teardown()
        with pytest.raises(RuntimeError, match="torn down"):
            await env.observe()

    asyncio.run(run())


def test_estimated_effort_cost_capability_requires_repo_payload() -> None:
    async def run() -> None:
        provider = ChatmanStateProvider()
        env = await provider.materialize(scenario=None, config={})
        capability = _CAPABILITY_BY_BINDING["estimated_effort_cost"]
        with pytest.raises(ValueError, match="payload.repo"):
            await env.actuate(capability, {})
        await env.teardown()

    asyncio.run(run())


def test_estimated_effort_cost_capability_returns_real_cost_for_this_repo() -> None:
    import os

    async def run() -> None:
        provider = ChatmanStateProvider()
        env = await provider.materialize(scenario=None, config={})
        capability = _CAPABILITY_BY_BINDING["estimated_effort_cost"]
        repo_path = os.path.expanduser("~/gymact")
        result = await env.actuate(capability, {"repo": repo_path, "since": "30 days ago"})
        assert result["result"]["unit"] == "engineering_hour"
        assert result["result"]["kind"] == "declared_estimate"
        assert result["result"]["quantity"] >= 0.0
        await env.teardown()

    asyncio.run(run())


def test_environment_rejects_unsupported_capability_binding() -> None:
    async def run() -> None:
        from gymact.models import Capability, Consequence

        provider = ChatmanStateProvider()
        env = await provider.materialize(scenario=None, config={})
        bogus = Capability(
            iri="urn:gymact:chatman-state:capability:not-real",
            title="not real",
            consequence=Consequence.READ,
            binding="not_a_real_binding",
        )
        with pytest.raises(ValueError, match="unsupported chatman-state binding"):
            await env.actuate(bogus, {})
        await env.teardown()

    asyncio.run(run())
