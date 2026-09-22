"""Real GymAct `Environment`/`EnvironmentProvider` that treats an arbitrary
MCP server as the subject world, mediated by a real `fastmcp.Client` session.

Target selection for this module: `~/autofde-lab/vendor/gyms/mcpmark` does
not exist in this checkout (`ls` came back empty), so there is no externally
documented MCP-server-start command to point this adapter at. The fallback
target is GymAct's own `gymact.surfaces.fastmcp.create_mcp()` server,
addressed generically as "a subject MCP server" from the client's point of
view -- this module never imports GymAct-specific tool names or reaches into
`create_mcp()`'s internals; it only calls `client.list_tools()` and
`client.call_tool()`, exactly as it would against any other real MCP server.

`materialize()` really constructs the target `FastMCP` server object
in-process and opens a real `fastmcp.Client` against it over FastMCP's
in-memory transport (a real MCP session handshake, not a stub) -- no server
subprocess is required because the target here is an in-process object, not
an external command. `list_tools`/`call_tool` capabilities are backed by real
`client.list_tools()` / `client.call_tool()` calls; there is no simulated
tool catalog or canned tool result anywhere in this module.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from fastmcp import Client, FastMCP

from gymact.models import Capability, Consequence

MCP_LIST_TOOLS_CAPABILITY = Capability(
    iri="urn:gymact:mcp-client-session:capability:list_tools",
    title="List the real tools currently exposed by the subject MCP server",
    consequence=Consequence.READ,
    binding="list_tools",
)

MCP_CALL_TOOL_CAPABILITY = Capability(
    iri="urn:gymact:mcp-client-session:capability:call_tool",
    title="Call a named, side-effect-safe tool on the subject MCP server",
    consequence=Consequence.DO,
    binding="call_tool",
)


class McpClientSessionEnvironment:
    """Wraps one real `fastmcp.Client` session against one real subject MCP
    server. The subject is opaque to this class beyond FastMCP's own
    `Client`/`FastMCP` types -- it does not know or care whether the target
    is `gymact`'s own `create_mcp()` server or an external one, matching
    `discovered.py`'s "generic adapter, not a per-subject class" posture.
    """

    def __init__(
        self,
        *,
        server: FastMCP,
        client: Client,
        safe_call_tool_name: str | None,
        safe_call_tool_args: dict[str, Any],
        requires_authority: bool = False,
    ) -> None:
        self.environment_id = f"urn:gymact:mcp-client-session:environment:{uuid4().hex}"
        self.requires_authority = requires_authority
        self._server = server
        self._client = client
        self._safe_call_tool_name = safe_call_tool_name
        self._safe_call_tool_args = safe_call_tool_args
        self._closed = False

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError("environment is torn down")

    def capabilities(self) -> tuple[Capability, ...]:
        self._ensure_open()
        if self._safe_call_tool_name is None:
            return (MCP_LIST_TOOLS_CAPABILITY,)
        return (MCP_LIST_TOOLS_CAPABILITY, MCP_CALL_TOOL_CAPABILITY)

    async def _tool_names(self) -> list[str]:
        tools = await self._client.list_tools()
        return sorted(tool.name for tool in tools)

    async def observe(self) -> dict[str, Any]:
        self._ensure_open()
        return {"tool_names": await self._tool_names()}

    async def actuate(self, capability: Capability, payload: dict[str, Any]) -> dict[str, Any]:
        del payload
        self._ensure_open()
        binding = capability.binding
        if binding == "list_tools":
            before = await self._tool_names()
            after = await self._tool_names()
            return {"before": {"tool_names": before}, "after": {"tool_names": after}}
        if binding == "call_tool":
            if self._safe_call_tool_name is None:
                raise ValueError("no safe call_tool target configured for this subject server")
            before = await self._tool_names()
            result = await self._client.call_tool(
                self._safe_call_tool_name, self._safe_call_tool_args
            )
            after = await self._tool_names()
            return {
                "before": {"tool_names": before},
                "after": {"tool_names": after},
                "result_text": [block.model_dump(mode="json") for block in result.content],
            }
        raise ValueError(f"unsupported mcp-client-session binding: {binding}")

    async def verify(self, expected: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
        self._ensure_open()
        observed = await self.observe()
        passed = all(observed.get(key) == value for key, value in expected.items())
        return passed, observed

    async def checkpoint(self) -> dict[str, Any]:
        self._ensure_open()
        return await self.observe()

    async def restore(self, checkpoint: dict[str, Any]) -> None:
        # The subject MCP server's tool catalog is not GymAct-owned state --
        # there is nothing for this adapter to write back. Restoring is a
        # real no-op against real, already-authoritative server state, not a
        # simulated round trip.
        self._ensure_open()
        del checkpoint

    async def teardown(self) -> None:
        if not self._closed:
            await self._client.__aexit__(None, None, None)
        self._closed = True


class McpClientSessionProvider:
    """GymAct `EnvironmentProvider` that materializes a real `fastmcp.Client`
    session against a real subject `FastMCP` server.

    `config["server_factory"]` must be a zero-argument callable returning a
    real `fastmcp.FastMCP` instance (defaults to `gymact`'s own
    `create_mcp()` -- the documented fallback target for this module).
    `config["safe_call_tool"]` optionally names a real, side-effect-free tool
    on that server (`{"name": ..., "args": {...}}`) to back the `call_tool`
    DO capability; omitted, the environment exposes `list_tools` only.
    """

    name = "mcp-client-session"
    materialization_requires_authority = False

    async def materialize(
        self, *, scenario: str | None, config: dict[str, Any]
    ) -> McpClientSessionEnvironment:
        del scenario
        server_factory = config.get("server_factory")
        if server_factory is None:
            from gymact.surfaces.fastmcp import create_mcp

            server_factory = create_mcp
        if not callable(server_factory):
            raise TypeError("config.server_factory must be callable")
        server = server_factory()
        if not isinstance(server, FastMCP):
            raise TypeError("config.server_factory must return a fastmcp.FastMCP instance")

        safe_call_tool = config.get("safe_call_tool")
        safe_call_tool_name: str | None = None
        safe_call_tool_args: dict[str, Any] = {}
        if safe_call_tool is not None:
            if not isinstance(safe_call_tool, dict) or "name" not in safe_call_tool:
                raise TypeError('config.safe_call_tool must be {"name": str, "args": dict?}')
            safe_call_tool_name = str(safe_call_tool["name"])
            safe_call_tool_args = dict(safe_call_tool.get("args", {}))

        requires_authority = config.get("requires_authority", False)
        if not isinstance(requires_authority, bool):
            raise TypeError("config.requires_authority must be a boolean")

        client = Client(server)
        await client.__aenter__()
        return McpClientSessionEnvironment(
            server=server,
            client=client,
            safe_call_tool_name=safe_call_tool_name,
            safe_call_tool_args=safe_call_tool_args,
            requires_authority=requires_authority,
        )
