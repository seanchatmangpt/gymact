"""FastMCP surface over GymAct's semantic runtime."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from fastmcp import FastMCP

from gymact.models import ActuationIntent, MaterializationIntent
from gymact.providers import MemoryProvider
from gymact.runtime import GymAct

_PROBE_MAX_CHARS = 4000


def _runtime(runtime: GymAct | None) -> GymAct:
    if runtime is not None:
        return runtime
    instance = GymAct()
    instance.register_provider(MemoryProvider())
    return instance


def create_mcp(runtime: GymAct | None = None) -> FastMCP:
    """Create generic GymAct MCP tools; benchmark identity remains data."""
    service = _runtime(runtime)
    mcp = FastMCP("GymAct")

    @mcp.tool()
    async def discover() -> list[str]:
        """List registered environment providers."""
        return list(service.discover())

    @mcp.tool()
    async def create_episode(
        provider: str = "memory",
        scenario: str | None = None,
        config: dict[str, Any] | None = None,
        authority_ref: str | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        """Materialize one bounded environment episode with a receipted disposition."""
        values: dict[str, Any] = {
            "provider": provider,
            "scenario": scenario,
            "config": config or {},
            "authority_ref": authority_ref,
        }
        if idempotency_key is not None:
            values["idempotency_key"] = idempotency_key
        result = await service.materialize(MaterializationIntent.model_validate(values))
        return result.model_dump(mode="json")

    @mcp.tool()
    async def capabilities(episode_id: str) -> list[dict[str, Any]]:
        """List admitted semantic capabilities for a materialized environment."""
        return [item.model_dump(mode="json") for item in service.capabilities(episode_id)]

    @mcp.tool()
    async def observe(episode_id: str) -> dict[str, Any]:
        """Observe current environment state without claiming verification."""
        return (await service.observe(episode_id)).model_dump(mode="json")

    @mcp.tool()
    async def act(
        episode_id: str,
        capability: str,
        payload: dict[str, Any] | None = None,
        authority_ref: str | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        """Submit a semantic actuation intent; MCP transport itself grants no authority."""
        values: dict[str, Any] = {
            "episode_id": episode_id,
            "capability": capability,
            "payload": payload or {},
            "authority_ref": authority_ref,
        }
        if idempotency_key is not None:
            values["idempotency_key"] = idempotency_key
        intent = ActuationIntent.model_validate(values)
        return (await service.act(intent)).model_dump(mode="json")

    @mcp.tool()
    async def verify(episode_id: str, expected: dict[str, Any]) -> dict[str, Any]:
        """Independently verify expected partial state."""
        return (await service.verify(episode_id, expected)).model_dump(mode="json")

    @mcp.tool()
    async def checkpoint(episode_id: str) -> dict[str, Any]:
        """Capture provider-defined recovery state."""
        return {"checkpoint": await service.checkpoint(episode_id)}

    @mcp.tool()
    async def restore(
        episode_id: str, checkpoint: dict[str, Any], authority_ref: str | None = None
    ) -> dict[str, Any]:
        """Restore checkpoint state under the same authority rules as actuation."""
        return (
            await service.restore(episode_id, checkpoint, authority_ref=authority_ref)
        ).model_dump(mode="json")

    @mcp.tool()
    async def probe_repo(subject_path: str) -> dict[str, Any]:
        """Read-only probe of a real repository directory: README, pyproject/
        setup.py (whichever exists), and top-level file listing, truncated.

        This is the only new read surface an LLM-driven discovery loop gets --
        no shell access, no arbitrary code execution granted here. What to do
        with this information (propose a real command) is the caller's job;
        actually running it goes through GymAct's own actuate()/authority
        path like every other consequential operation.
        """
        root = Path(subject_path)
        if not root.is_dir():
            return {"exists": False, "subject_path": subject_path}

        def _read(name: str) -> str | None:
            path = root / name
            if not path.is_file():
                return None
            try:
                return path.read_text(errors="replace")[:_PROBE_MAX_CHARS]
            except OSError:
                return None

        readme = None
        for candidate in ("README.md", "README.rst", "README.txt", "README"):
            readme = _read(candidate)
            if readme is not None:
                break

        try:
            top_level = sorted(os.listdir(root))[:100]
        except OSError:
            top_level = []

        return {
            "exists": True,
            "subject_path": subject_path,
            "readme": readme,
            "pyproject_toml": _read("pyproject.toml"),
            "setup_py": _read("setup.py"),
            "top_level_files": top_level,
        }

    @mcp.tool()
    async def teardown(episode_id: str, authority_ref: str | None = None) -> dict[str, Any]:
        """Idempotently tear down one environment episode."""
        return (await service.teardown(episode_id, authority_ref=authority_ref)).model_dump(
            mode="json"
        )

    return mcp
