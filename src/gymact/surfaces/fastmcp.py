"""FastMCP surface over GymAct's semantic runtime."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from fastmcp import FastMCP

from gymact.brce import BRCEBroker, BrokerRequest
from gymact.cut import CombinatorialBrokerRequest
from gymact.dcm_runtime import DCMDecisionCourt, DecisionCourtRequest
from gymact.ggen_agent import GgenAgentRuntime, manufacture_ggen_agent_space
from gymact.models import ActuationIntent, MaterializationIntent
from gymact.providers import MemoryProvider
from gymact.runtime import GymAct, ProductionGymAct
from gymact.transport import TransportKind, normalize_candidate

_PROBE_MAX_CHARS = 4000


def _runtime(runtime: GymAct | None) -> GymAct:
    if runtime is not None:
        return runtime
    instance = ProductionGymAct()
    instance.register_provider(MemoryProvider())
    return instance


def create_mcp(
    runtime: GymAct | None = None,
    *,
    ggen_agents: GgenAgentRuntime | None = None,
) -> FastMCP:
    """Create GymAct MCP tools; DCM selected-cut execution is the production DO mode.

    ``ggen_agents`` is an optional LLM-free logical-agent runtime. Its three
    tools are registered only when that runtime is supplied, so the default
    production surface remains exactly the ontology-admitted ten-tool bridge.
    MCP is transport, never a reasoner.
    """
    service = _runtime(runtime)
    compatibility_broker = BRCEBroker(service)
    decision_court = DCMDecisionCourt()
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

    if ggen_agents is not None:

        async def ggen_agent_catalog() -> dict[str, Any]:
            """List configured LLM-free logical ggen agents and current active WIP."""
            return {
                "standing": "ALIVE",
                "agents": [spec.model_dump(mode="json") for spec in ggen_agents.specs()],
                "wip": ggen_agents.wip(),
                "llm_calls": 0,
            }

        async def ggen_agent_frontier(
            roles: list[str],
            planners: list[str],
            objectives: list[str],
            observation_projections: list[str],
            action_projections: list[str],
            packs: list[str],
            max_combinations: int = 10000,
        ) -> dict[str, Any]:
            """Construct a powerless DfCM logical-agent possibility space without selecting."""
            space = manufacture_ggen_agent_space(
                roles=tuple(roles),
                planners=tuple(planners),
                objectives=tuple(objectives),
                observation_projections=tuple(observation_projections),
                action_projections=tuple(action_projections),
                packs=tuple(packs),
                max_combinations=max_combinations,
            )
            return {"mode": "CONSTRUCT", "llm_calls": 0, **space.model_dump(mode="json")}

        async def ggen_agent_invoke(
            agent_id: str,
            observation: dict[str, Any],
            inputs: dict[str, Any] | None = None,
        ) -> dict[str, Any]:
            """Invoke one deterministic logical ggen agent; no LM is instantiated."""
            result = await ggen_agents.invoke(
                agent_id,
                observation=observation,
                inputs=inputs or {},
            )
            return result.model_dump(mode="json")

        mcp.tool()(ggen_agent_catalog)
        mcp.tool()(ggen_agent_frontier)
        mcp.tool()(ggen_agent_invoke)

    @mcp.tool()
    async def act(
        episode_id: str | None = None,
        capability: str | None = None,
        payload: dict[str, Any] | None = None,
        authority_ref: str | None = None,
        idempotency_key: str | None = None,
        candidate: dict[str, Any] | None = None,
        court: dict[str, Any] | None = None,
        selected: dict[str, Any] | None = None,
        request: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """One transport, explicit authority phases.

        ``candidate`` is powerless CONSTRUCT. ``court`` admits/explores a public RDF
        possibility graph. ``selected`` is canonical DO and must contain a DCM cut-bound
        request. ``request`` is deprecated BRCE compatibility. Legacy fields cannot
        mutate the default ProductionGymAct runtime.
        """
        supplied = sum(value is not None for value in (candidate, court, selected, request))
        legacy_supplied = episode_id is not None or capability is not None
        if supplied + int(legacy_supplied) != 1:
            raise ValueError("ACT_REQUIRES_EXACTLY_ONE_MODE")

        if candidate is not None:
            envelope = normalize_candidate(TransportKind.MCP, candidate)
            return {
                "mode": "CONSTRUCT",
                "semantic_key": envelope.semantic_key(),
                "prepared": envelope.prepared().model_dump(mode="json"),
            }

        if court is not None:
            court_request = DecisionCourtRequest.model_validate(court)
            result = decision_court.admit_request(court_request)
            return {"mode": "MAXIMAL_CLOSURE", "court": result.model_dump(mode="json")}

        if selected is not None:
            cut_request = CombinatorialBrokerRequest.model_validate(selected)
            prepared_episode = cut_request.broker_request.prepared.episode_id
            if episode_id is not None and prepared_episode != episode_id:
                raise ValueError("EPISODE_ID_PATH_BODY_MISMATCH")
            transition = await decision_court.execute(service, cut_request)
            return {"mode": "DCM_DO", "transition": transition.model_dump(mode="json")}

        if request is not None:
            broker_request = BrokerRequest.model_validate(request)
            transition = await compatibility_broker.execute(broker_request)
            return {
                "mode": "COMPATIBILITY_DO",
                "transition": transition.model_dump(mode="json"),
            }

        if episode_id is None or capability is None:
            raise ValueError("LEGACY_ACT_REQUIRES_EPISODE_AND_CAPABILITY")
        values: dict[str, Any] = {
            "episode_id": episode_id,
            "capability": capability,
            "payload": payload or {},
            "authority_ref": authority_ref,
        }
        if idempotency_key is not None:
            values["idempotency_key"] = idempotency_key
        intent = ActuationIntent.model_validate(values)
        result = await service.act(intent)
        return {"mode": "LEGACY", **result.model_dump(mode="json")}

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
        episode_id: str,
        checkpoint: dict[str, Any],
        authority_ref: str | None = None,
    ) -> dict[str, Any]:
        """Restore checkpoint state under the same authority rules as actuation."""
        return (
            await service.restore(episode_id, checkpoint, authority_ref=authority_ref)
        ).model_dump(mode="json")

    @mcp.tool()
    async def probe_repo(subject_path: str) -> dict[str, Any]:
        """Read-only bounded probe of a repository directory for discovery."""
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
        for candidate_name in ("README.md", "README.rst", "README.txt", "README"):
            readme = _read(candidate_name)
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
