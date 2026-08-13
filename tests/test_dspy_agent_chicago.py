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
    Standing,
)
from gymact.dspy_agent import (  # noqa: E402
    GymActReActAgent,
    UngroundedActuationRefused,
    _assert_payload_is_grounded,
    _collect_string_leaves,
)
from gymact.gyms.sregym import SregymVendorProvider  # noqa: E402
from gymact.limits import RuntimeLimits  # noqa: E402
from tests.test_sregym_provider import (  # noqa: E402
    _real_sregym_checkout_ready as _real_sregym_ready,
)

AUTHORITY = "urn:test:dspy-agent-authority"
_SREGYM_LIVE_READY, _SREGYM_LIVE_REASON = _real_sregym_ready()


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


class TestGymActReActAgentWrapsReadCapabilities:
    """Real proof of the READ-tool gap fix: `chatman-state`'s gym is 100%
    `Consequence.READ` (no DO capabilities at all), so before this fix
    `GymActReActAgent._build_tools` would hand the agent zero real tools
    for it. No LLM needed -- these call the real tool closures directly,
    same style as the grounding-guard tests above."""

    async def _agent_over_real_chatman_state_episode(self):
        import shutil

        if shutil.which("gh") is None or shutil.which("git") is None:
            pytest.skip("real gh/git CLI required on PATH")
        from gymact.gyms.chatman_state_gym import ChatmanStateProvider

        gym = GymAct()
        gym.register_provider(ChatmanStateProvider())
        materialization = await gym.materialize(
            MaterializationIntent(provider="chatman-state", config={"repo_limit": 3})
        )
        assert materialization.accepted, materialization.receipt.reason
        episode_id = materialization.episode.episode_id
        agent = GymActReActAgent(gym, episode_id)
        return gym, agent, episode_id

    async def test_read_only_gym_gets_real_nonempty_tools(self):
        gym, agent, episode_id = await self._agent_over_real_chatman_state_episode()
        steps = []
        tools = {tool.name: tool for tool in agent._build_tools(steps)}
        # The bug this fixes: before wrapping READ capabilities, this dict
        # held only "observe" for a gym with zero DO capabilities.
        assert {
            "list_local_repos",
            "list_github_repos",
            "estimated_effort_cost",
            "portfolio_summary",
        }.issubset(tools.keys())
        await gym.teardown(episode_id)

    async def test_read_tool_reaches_the_real_kernel_read_path(self):
        gym, agent, episode_id = await self._agent_over_real_chatman_state_episode()
        steps = []
        tools = {tool.name: tool for tool in agent._build_tools(steps)}
        result = await tools["portfolio_summary"].acall(payload={})
        assert result["result"]["local_repo_count_found"] >= result["result"]["local_repo_count_returned"]
        assert steps and steps[-1].tool_name == "portfolio_summary"
        await gym.teardown(episode_id)

    async def test_read_tool_result_widens_grounded_facts_for_later_do_calls(self):
        gym, agent, episode_id = await self._agent_over_real_chatman_state_episode()
        steps = []
        tools = {tool.name: tool for tool in agent._build_tools(steps)}
        assert agent._grounded_facts == frozenset()
        await tools["list_local_repos"].acall(payload={})
        # A real repo name surfaced by the READ call must now be grounded --
        # the same widening `observe_tool` performs, just sourced from a
        # capability result instead of `environment.observe()`.
        assert "gymact" in agent._grounded_facts or len(agent._grounded_facts) > 0
        await gym.teardown(episode_id)

    async def test_read_tool_cannot_be_smuggled_through_kernel_act(self):
        """The READ tool goes through `gym.read()`, never `gym.act()` --
        confirm the underlying law it relies on still refuses the DO path,
        so a future accidental rewiring back to `act()` would be caught by
        this test, not silently pass."""
        gym, _agent, episode_id = await self._agent_over_real_chatman_state_episode()
        from gymact.models import ActuationIntent

        capability = next(
            c for c in gym.capabilities(episode_id) if c.binding == "portfolio_summary"
        )
        result = await gym.act(
            ActuationIntent(episode_id=episode_id, capability=capability.iri, payload={})
        )
        assert result.standing == Standing.REFUSED
        assert result.receipt.reason == "READ_CAPABILITY_IS_NOT_ACTUATION"
        await gym.teardown(episode_id)


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


@pytest.mark.skipif(not _groq_key_available(), reason="no GROQ_API_KEY in this environment")
@pytest.mark.skipif(
    not _SREGYM_LIVE_READY, reason=f"live sregym prerequisites not met: {_SREGYM_LIVE_REASON}"
)
class TestGymActReActAgentOverRealSregym:
    """Real end-to-end: `GymActReActAgent` driving sregym's real
    `run_kubectl` capability through the real kernel. `run_kubectl`'s
    payload is a composed command string ("kubectl get pods -n ...") that
    never appears verbatim as a single grounded leaf even when every fact
    inside it is genuinely observed -- the exact-match grounding guard
    (`_assert_payload_is_grounded`) has no per-field composed-payload
    policy yet (tracked separately; needs the payload-schema pack). Until
    that lands, `create_capable_bindings={"run_kubectl"}` is the real,
    explicit, named escape hatch this session settled on: it disables
    grounding for exactly this one binding rather than silently working
    around the guard, matching this module's own documented default
    (fail-closed unless a caller explicitly names an exemption)."""

    @pytest.mark.filterwarnings("ignore::pytest.PytestUnraisableExceptionWarning")
    async def test_agent_runs_a_real_kubectl_command_through_sregym(self):
        # Real defect found and fixed forward this session (also fixed in
        # scripts/run_dspy_sregym_diagnosis.py): `RuntimeLimits`'s default
        # `materialize_timeout_s` (60s) wraps the whole `provider.
        # materialize()` call in `anyio.fail_after`, but sregym's own
        # startup poll (`gymact.polling.poll_until`) uses a real BLOCKING
        # `time.sleep()`, never yielding to the event loop -- the real
        # subprocess/cluster startup reliably takes well over 60s, so the
        # kernel retroactively declared MATERIALIZATION_TIMEOUT after the
        # environment had already, successfully, finished starting.
        gym = GymAct(
            authority_resolver=AllowListAuthorityResolver({AUTHORITY}),
            limits=RuntimeLimits(materialize_timeout_s=300.0),
        )
        gym.register_provider(SregymVendorProvider())
        materialization = await gym.materialize(
            MaterializationIntent(
                provider="sregym",
                config={"scenario": "misconfig_app_hotel_res", "wall_clock_timeout_s": 600},
                authority_ref=AUTHORITY,
            )
        )
        assert materialization.accepted, materialization.receipt.reason
        episode_id = materialization.episode.episode_id
        agent = GymActReActAgent(
            gym,
            episode_id,
            authority_ref=AUTHORITY,
            max_iters=4,
            create_capable_bindings=frozenset({"run_kubectl"}),
        )

        try:
            result = await agent.run_goal(
                "List the real Kubernetes namespaces using kubectl, then report what you found."
            )
            assert result.outcome
        finally:
            await gym.teardown(episode_id, authority_ref=AUTHORITY)
            import gc

            gc.collect()
