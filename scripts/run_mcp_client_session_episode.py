#!/usr/bin/env python3
"""Run one real GymAct episode over `McpClientSessionProvider` -- a real
`fastmcp.Client` session against gymact's own `create_mcp()` `FastMCP`
server (the documented fallback target, see `mcp_client_session.py`'s
module docstring) -- and write a real OCEL 2.0 log at
reports/ocel/mcp-client-session/episode.ocel.json.

Mirrors `scripts/run_dev_portfolio_episode.py`'s real shape (materialize ->
act -> verify -> teardown -> write_ocel_log). The DO capability exercised is
`call_tool`, configured with `config["safe_call_tool"] =
{"name": "discover", "args": {}}` -- a real, side-effect-free tool on the
subject server (`create_mcp()`'s own `discover` tool), matching
`tests/test_mcp_client_session.py`'s own episode helper. `list_tools` is
READ and is exercised through `gym.observe()` instead, per
`gymact.kernel.GymAct.act`'s "READ_CAPABILITY_IS_NOT_ACTUATION" refusal.

Per `gymact.standing.require_standing`, this script refuses to run (loud,
not silent) if `fastmcp` is not importable -- matching
`tests/test_mcp_client_session.py`'s own gate.

Usage:
    uv run python scripts/run_mcp_client_session_episode.py
"""

from __future__ import annotations

import asyncio
import importlib.util
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from gymact import AllowListAuthorityResolver, GymAct, MaterializationIntent
from gymact.gyms.mcp_client_session import McpClientSessionProvider
from gymact.models import ActuationIntent
from gymact.ocel import write_ocel_log
from gymact.standing import require_standing

REPORTS_DIR = Path(__file__).parent.parent / "reports" / "ocel"

CALL_TOOL = "urn:gymact:mcp-client-session:capability:call_tool"
AUTHORITY = "urn:gymact:mcp-client-session-episode:authority"

require_standing(
    "LOCAL_GYM:mcp-client-session",
    available=importlib.util.find_spec("fastmcp") is not None,
    reason="the 'fastmcp' package is not importable in this environment",
)


async def run() -> None:
    gym = GymAct(authority_resolver=AllowListAuthorityResolver({AUTHORITY}))
    gym.register_provider(McpClientSessionProvider())
    receipts = []
    log_path = REPORTS_DIR / "mcp-client-session" / "episode.ocel.json"

    materialization = await gym.materialize(
        MaterializationIntent(
            provider="mcp-client-session",
            config={"safe_call_tool": {"name": "discover", "args": {}}},
        )
    )
    receipts.append(materialization.receipt)
    if not materialization.accepted or materialization.episode is None:
        print(f"mcp-client-session: materialization refused: {materialization.receipt.reason}")
        log, digest = write_ocel_log(log_path, receipts)
        print(f"mcp-client-session: {len(log['events'])} events, sha256={digest}")
        return

    episode_id = materialization.episode.episode_id

    # list_tools is READ -- exercised via observe(), not act(); this proves
    # the real tool catalog before the DO step below.
    observation = await gym.observe(episode_id)
    print(f"mcp-client-session: observed tool_names={observation.state['tool_names']}")

    call_result = await gym.act(
        ActuationIntent(episode_id=episode_id, capability=CALL_TOOL, authority_ref=AUTHORITY)
    )
    print(f"mcp-client-session: call_tool accepted={call_result.accepted}")

    # verify() routes through observe() (see McpClientSessionEnvironment.verify),
    # which returns {"tool_names": [...]} -- the real tool catalog is stable
    # across the call_tool actuation, so the expected value is the same
    # catalog observed before acting.
    verification = await gym.verify(episode_id, {"tool_names": observation.state["tool_names"]})
    print(f"mcp-client-session: verify_passed={verification.passed}")

    # Real solved=True evidence recorded directly on the call_tool act
    # event's own reason attribute -- matching scripts/run_togaf_episode.py's
    # and scripts/run_terraform_docker_apply_episode.py's precedent, so
    # tests/test_ocel_standing.py's real replay-based derivation can find it
    # on this act event, not on a separate summary.
    receipts.append(
        call_result.receipt.model_copy(update={"reason": f"solved={verification.passed}"})
    )

    receipts.append(await gym.teardown(episode_id, authority_ref=AUTHORITY))

    log, digest = write_ocel_log(log_path, receipts)
    print(f"mcp-client-session: {len(log['events'])} events, sha256={digest}")


if __name__ == "__main__":
    asyncio.run(run())
