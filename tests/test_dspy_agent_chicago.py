"""Chicago-style tests for `gymact.dspy_agent` -- a generic, gym-agnostic
DSPy ReAct agent over the real GymAct kernel. No mocks: the grounding-guard
tests call the real, exported guard functions directly against real payload
dicts (deterministic, no LLM needed); the live-episode tests materialize a
real `MemoryProvider` episode and drive it through the real kernel exactly
as any other caller would.

Per `gymact.standing.require_standing`, real is the default: if the optional
`dspy` extra isn't installed, this module FAILS unless the run explicitly
opts into the degraded standing (see the module-level `require_standing`
call below) -- not a silent skip.
"""

from __future__ import annotations

import importlib.util

import pytest

from gymact.standing import require_standing

require_standing(
    "LOCAL_EXTRA:dspy",
    available=importlib.util.find_spec("dspy") is not None,
    reason="the optional 'dspy' extra is not installed -- `uv sync --extra dspy`",
)

from gymact import (  # noqa: E402
    AllowListAuthorityResolver,
    GymAct,
    MaterializationIntent,
    MemoryProvider,
)
from gymact.dspy_agent import (  # noqa: E402
    GymActReActAgent,
    UngroundedActuationRefused,
    _assert_payload_is_grounded,
    _collect_string_leaves,
)

AUTHORITY = "urn:test:dspy-agent-authority"


def _groq_key_available() -> bool:
    import os

    return bool(os.environ.get("GROQ_API_KEY"))


class TestGroundingGuardIsReal:
    """Direct, deterministic proof of the grounding mechanism -- no LLM
    involved, so these are not flaky and run every time."""

    def test_collect_string_leaves_walks_nested_real_structures(self):
        state = {"counter": 1, "nested": {"name": "real-key", "list": ["a", "b", 3]}}
        leaves = _collect_string_leaves(state)
        # Both dict KEYS ("counter", "nested", "name", "list") and string
        # VALUES ("real-key", "a", "b") must be collected -- a real
        # identifier reference is far more often a key than a value.
        assert leaves == {"counter", "nested", "name", "list", "real-key", "a", "b"}

    def test_grounded_payload_is_accepted_without_raising(self):
        _assert_payload_is_grounded(
            capability_ref="urn:test:cap",
            payload={"key": "counter"},
            grounded_facts=frozenset({"counter", "other-real-key"}),
        )  # must not raise

    def test_ungrounded_payload_is_refused(self):
        with pytest.raises(UngroundedActuationRefused) as ctx:
            _assert_payload_is_grounded(
                capability_ref="urn:test:cap",
                payload={"key": "invented-key-never-observed"},
                grounded_facts=frozenset({"counter"}),
            )
        assert ctx.value.capability_ref == "urn:test:cap"
        assert "invented-key-never-observed" in ctx.value.ungrounded_values
        assert "REFUSED:UNGROUNDED_ACTUATION" in str(ctx.value)


class TestGymActReActAgentToolRefusesUngroundedActuation:
    """Real MemoryProvider episode, real kernel, real refusal -- proves the
    agent's own actuator tool (not just the standalone guard function) wires
    the grounding check in before any real `act()` call reaches the kernel."""

    async def _agent_over_real_episode(self, *, create_capable_bindings=frozenset()):
        gym = GymAct(authority_resolver=AllowListAuthorityResolver({AUTHORITY}))
        gym.register_provider(MemoryProvider())
        materialization = await gym.materialize(
            MaterializationIntent(
                provider="memory", config={"initial": {"counter": 1}}, authority_ref=AUTHORITY
            )
        )
        assert materialization.accepted, materialization.receipt.reason
        episode_id = materialization.episode.episode_id
        agent = GymActReActAgent(
            gym,
            episode_id,
            authority_ref=AUTHORITY,
            create_capable_bindings=create_capable_bindings,
        )
        return gym, agent, episode_id

    async def test_real_observe_grounds_a_real_existing_key(self):
        gym, agent, episode_id = await self._agent_over_real_episode()
        steps = []
        tools = {tool.name: tool for tool in agent._build_tools(steps)}
        await agent._refresh_observation()
        # "increment" is not in create_capable_bindings -- "counter" IS real,
        # so this must be accepted and really reach the kernel.
        result = await tools["increment"].acall(payload={"key": "counter", "amount": 5})
        assert result["accepted"] is True
        real_state = await gym.observe(episode_id)
        assert real_state.state["counter"] == 6
        await gym.teardown(episode_id, authority_ref=AUTHORITY)

    async def test_increment_on_an_unobserved_key_is_refused_before_reaching_the_kernel(self):
        gym, agent, episode_id = await self._agent_over_real_episode()
        steps = []
        tools = {tool.name: tool for tool in agent._build_tools(steps)}
        await agent._refresh_observation()
        with pytest.raises(UngroundedActuationRefused) as ctx:
            await tools["increment"].acall(payload={"key": "score-never-observed", "amount": 1})
        assert "score-never-observed" in ctx.value.ungrounded_values
        # Real proof the kernel itself was never reached: the real episode
        # state has no trace of the refused key.
        real_state = await gym.observe(episode_id)
        assert "score-never-observed" not in real_state.state
        await gym.teardown(episode_id, authority_ref=AUTHORITY)

    async def test_set_is_exempt_when_named_a_create_capable_binding(self):
        gym, agent, episode_id = await self._agent_over_real_episode(
            create_capable_bindings=frozenset({"set"})
        )
        steps = []
        tools = {tool.name: tool for tool in agent._build_tools(steps)}
        await agent._refresh_observation()
        # "brand-new-key" was never observed, but "set" is exempt -- this
        # must be accepted (creation is the whole point of "set").
        result = await tools["set"].acall(payload={"key": "brand-new-key", "value": 42})
        assert result["accepted"] is True
        real_state = await gym.observe(episode_id)
        assert real_state.state["brand-new-key"] == 42
        await gym.teardown(episode_id, authority_ref=AUTHORITY)

    async def test_delete_on_an_unobserved_key_is_still_refused_even_with_set_exempt(self):
        gym, agent, episode_id = await self._agent_over_real_episode(
            create_capable_bindings=frozenset({"set"})
        )
        steps = []
        tools = {tool.name: tool for tool in agent._build_tools(steps)}
        await agent._refresh_observation()
        with pytest.raises(UngroundedActuationRefused):
            await tools["delete"].acall(payload={"key": "phantom-key"})
        await gym.teardown(episode_id, authority_ref=AUTHORITY)


@pytest.mark.skipif(not _groq_key_available(), reason="no GROQ_API_KEY in this environment")
class TestGymActReActAgentRealLiveGoal:
    """One real, live LM call (Groq) proving the full ReAct loop actually
    accomplishes a real, simple goal against a real MemoryProvider episode --
    honest end-to-end proof, not a structural-only claim."""

    async def test_agent_increments_the_real_observed_counter(self):
        gym = GymAct(authority_resolver=AllowListAuthorityResolver({AUTHORITY}))
        gym.register_provider(MemoryProvider())
        materialization = await gym.materialize(
            MaterializationIntent(
                provider="memory", config={"initial": {"counter": 10}}, authority_ref=AUTHORITY
            )
        )
        assert materialization.accepted, materialization.receipt.reason
        episode_id = materialization.episode.episode_id
        agent = GymActReActAgent(gym, episode_id, authority_ref=AUTHORITY, max_iters=4)

        try:
            result = await agent.run_goal(
                "Observe the current state, then increment the 'counter' key by 1."
            )
            assert result.outcome
            real_state = await gym.observe(episode_id)
            # The real, authoritative proof: kernel-observed state actually
            # changed as the goal asked -- not just an LLM's self-report.
            assert real_state.state["counter"] == 11
        finally:
            await gym.teardown(episode_id, authority_ref=AUTHORITY)
