"""Chicago-style: a real GymAct episode driven against a real subject MCP
server through a real `fastmcp.Client` session.

Target: `~/autofde-lab/vendor/gyms/mcpmark` does not exist in this checkout,
so there is no externally documented "start the MCP server" command to
target -- this falls back to `gymact.surfaces.fastmcp.create_mcp()`'s own
`FastMCP` server, addressed generically as "a subject MCP server" the same
way `mcp_client_session.py` would address any other one: only through
`fastmcp.Client.list_tools()`/`call_tool()`, never through GymAct-specific
internals.

Per `gymact.standing.require_standing`, the real thing (an importable
`fastmcp` and a real in-process `FastMCP` server) is the default; this only
degrades to a named, visible skip if `fastmcp` genuinely cannot be imported,
and only when the run explicitly opts in via
`GYMACT_ALLOW_DEGRADED_STANDINGS=LOCAL_GYM:mcp-client-session` (or `"*"`).
"""

from __future__ import annotations

import importlib.util

from gymact.standing import require_standing

require_standing(
    "LOCAL_GYM:mcp-client-session",
    available=importlib.util.find_spec("fastmcp") is not None,
    reason="the 'fastmcp' package is not importable in this environment",
)

from gymact import AllowListAuthorityResolver, GymAct, MaterializationIntent  # noqa: E402
from gymact.gyms.mcp_client_session import McpClientSessionProvider  # noqa: E402
from gymact.models import ActuationIntent, Operation, Standing  # noqa: E402
from gymact.ocel import receipts_to_ocel, validate_ocel_log  # noqa: E402
from gymact.process import ConformanceChecker  # noqa: E402

# Capability identity is ontology-owned by ggen/protocol-gym-pack/mcp-consumers.ttl.
LIST_TOOLS = "urn:gymact:mcp:capability:list_tools"
CALL_TOOL = "urn:gymact:mcp:capability:call_tool"
# mcp_client_session.py's requires_authority now defaults to True (a real DO
# capability invoking a real subject MCP tool must not run unauthorized) --
# every act()-driving test below explicitly admits AUTHORITY.
AUTHORITY = "urn:test:mcp-client-session-authority"


def _authorized_gym() -> GymAct:
    gym = GymAct(authority_resolver=AllowListAuthorityResolver({AUTHORITY}))
    gym.register_provider(McpClientSessionProvider())
    return gym


async def _run_real_mcp_session_episode() -> list:
    gym = _authorized_gym()
    receipts = []

    materialization = await gym.materialize(
        MaterializationIntent(
            provider="mcp-client-session",
            config={"safe_call_tool": {"name": "discover", "args": {}}},
        )
    )
    assert materialization.accepted is True
    receipts.append(materialization.receipt)
    episode_id = materialization.episode.episode_id

    # list_tools is a READ capability -- exercised through the real
    # observe() path, which does not itself mint a receipt (matching
    # gymact.models.Observation carrying no `receipt` field).
    await gym.observe(episode_id)

    receipts.append(
        (
            await gym.act(
                ActuationIntent(
                    episode_id=episode_id, capability=CALL_TOOL, authority_ref=AUTHORITY
                )
            )
        ).receipt
    )

    receipts.append(await gym.teardown(episode_id, authority_ref=AUTHORITY))
    return receipts


async def test_real_materialize_opens_a_real_fastmcp_client_session() -> None:
    gym = GymAct()
    gym.register_provider(McpClientSessionProvider())

    materialization = await gym.materialize(
        MaterializationIntent(provider="mcp-client-session", config={})
    )
    assert materialization.accepted is True
    episode_id = materialization.episode.episode_id

    # The subject server (gymact's own create_mcp()) really exposes its own
    # named tools -- this is not a canned tool catalog.
    tool_names = materialization.observation.state["tool_names"]
    assert "discover" in tool_names
    assert "create_episode" in tool_names
    assert "observe" in tool_names
    assert "teardown" in tool_names

    await gym.teardown(episode_id)


async def test_call_tool_capability_really_invokes_the_subject_servers_discover_tool() -> None:
    gym = _authorized_gym()

    materialization = await gym.materialize(
        MaterializationIntent(
            provider="mcp-client-session",
            config={"safe_call_tool": {"name": "discover", "args": {}}},
        )
    )
    episode_id = materialization.episode.episode_id

    result = await gym.act(
        ActuationIntent(episode_id=episode_id, capability=CALL_TOOL, authority_ref=AUTHORITY)
    )
    assert result.accepted is True
    # The subject server's real `discover()` tool returns its registered
    # provider names as a JSON text block -- assert the real content came
    # back, not that a client method was merely called.
    result_text = result.effect["result_text"]
    assert result_text
    assert any("memory" in str(block) for block in result_text)

    await gym.teardown(episode_id, authority_ref=AUTHORITY)


async def test_list_tools_capability_observes_a_stable_real_tool_catalog() -> None:
    gym = GymAct()
    gym.register_provider(McpClientSessionProvider())

    materialization = await gym.materialize(
        MaterializationIntent(provider="mcp-client-session", config={})
    )
    episode_id = materialization.episode.episode_id

    # list_tools is READ; per gymact.kernel, a READ capability is refused by
    # act() ("READ_CAPABILITY_IS_NOT_ACTUATION") -- it is exercised through
    # the real observe() path instead, exactly like every other READ
    # capability in this codebase.
    first = await gym.observe(episode_id)
    second = await gym.observe(episode_id)
    assert first.state["tool_names"] == second.state["tool_names"]
    assert "discover" in first.state["tool_names"]

    await gym.teardown(episode_id)


async def test_mcp_session_episode_replays_conformant_and_produces_a_valid_ocel_log() -> None:
    receipts = await _run_real_mcp_session_episode()
    operations = [r.operation for r in receipts]

    assert operations == [
        Operation.MATERIALIZE,
        Operation.ACT,
        Operation.TEARDOWN,
    ]

    result = ConformanceChecker().check(operations)
    assert result.conformant is True

    log = receipts_to_ocel(receipts)
    validate_ocel_log(log)  # real jsonschema.validate against real OCEL 2.0 schema

    teardown_receipt = receipts[-1]
    assert teardown_receipt.standing == Standing.ALIVE
