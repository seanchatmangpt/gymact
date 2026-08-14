"""LLM-free logical agents backed by deterministic ggen manufacture.

An agent in this module is a projection, not a conversational process:

    Agent = Planner x Role x Objective x ObservationProjection x ActionProjection x Pack

The DfCM possibility space is preserved independently of active execution.  A
``GgenAgentRuntime`` admits only a bounded amount of active work and refuses
excess WIP rather than hiding it in an internal queue.  The manufacturer is
injected; the production adapter routes manufacture through GymAct's existing
``ggen`` provider and therefore through the normal authority/receipt boundary.

No class in this module constructs, requires, or calls an LLM.
"""
from __future__ import annotations

import inspect
from collections.abc import Callable, Mapping
from typing import Any, Literal, Protocol, runtime_checkable

import anyio
from pydantic import Field

from gymact.combinatorial import (
    CombinationSpace,
    ExplorationBounds,
    Factor,
    manufacture_combination_space,
)
from gymact.evidence import digest
from gymact.models import ActuationIntent, FrozenModel, Standing


class GgenAgentSpec(FrozenModel):
    """One powerless logical-agent projection over deterministic manufacture."""

    agent_id: str = Field(min_length=1)
    role_ref: str = Field(min_length=1)
    planner_ref: str = Field(min_length=1)
    objective_ref: str = Field(min_length=1)
    observation_projection_ref: str = Field(min_length=1)
    action_projection_ref: str = Field(min_length=1)
    pack_ref: str = Field(min_length=1)
    observation_keys: tuple[str, ...] = ()
    output_keys: tuple[str, ...] = ()
    max_wip: int = Field(default=1, ge=1, le=1024)
    mcp_tool_name: str | None = None


class GgenAgentResult(FrozenModel):
    """Receiptable result of one logical-agent manufacture invocation."""

    agent_id: str
    standing: Standing
    reason: str
    output: dict[str, Any] = Field(default_factory=dict)
    manufacturer_ref: str
    receipt_digest: str
    llm_calls: Literal[0] = 0


@runtime_checkable
class GgenManufacturer(Protocol):
    """Deterministic manufacture boundary consumed by logical agents."""

    manufacturer_ref: str

    async def manufacture(
        self,
        *,
        spec: GgenAgentSpec,
        observation: dict[str, Any],
        inputs: dict[str, Any],
    ) -> Mapping[str, Any]: ...


ManufactureCallable = Callable[..., Mapping[str, Any] | Any]


class CallableGgenManufacturer:
    """Small adapter for deterministic Python/ggen-generated callables.

    The callable may be synchronous or asynchronous.  It receives only the
    admitted projection plus explicit inputs; no prompt or language model is
    manufactured behind the caller's back.
    """

    manufacturer_ref = "urn:gymact:manufacturer:callable-ggen"

    def __init__(self, functions: Mapping[str, ManufactureCallable]) -> None:
        self._functions = dict(functions)

    async def manufacture(
        self,
        *,
        spec: GgenAgentSpec,
        observation: dict[str, Any],
        inputs: dict[str, Any],
    ) -> Mapping[str, Any]:
        function = self._functions.get(spec.agent_id)
        if function is None:
            raise KeyError(f"GGEN_AGENT_MANUFACTURER_MISSING:{spec.agent_id}")
        value = function(spec=spec, observation=observation, inputs=inputs)
        if inspect.isawaitable(value):
            value = await value
        if not isinstance(value, Mapping):
            raise TypeError("GGEN_AGENT_MANUFACTURER_MUST_RETURN_MAPPING")
        return value


class GymActGgenManufacturer:
    """Production adapter over an already-materialized GymAct ``ggen`` episode.

    This adapter does not shell out around GymAct.  It invokes the provider's
    existing ``sync`` capability through ``GymAct.act`` so authority,
    capability scope, idempotency, verification evidence, and receipts stay in
    the same kernel path as every other consequential operation.
    """

    manufacturer_ref = "urn:gymact:manufacturer:ggen-provider"

    def __init__(
        self,
        runtime: Any,
        episode_id: str,
        *,
        authority_ref: str | None = None,
        principal: str | None = None,
    ) -> None:
        self._runtime = runtime
        self._episode_id = episode_id
        self._authority_ref = authority_ref
        self._principal = principal

    async def manufacture(
        self,
        *,
        spec: GgenAgentSpec,
        observation: dict[str, Any],
        inputs: dict[str, Any],
    ) -> Mapping[str, Any]:
        del observation
        capabilities = self._runtime.capabilities(self._episode_id)
        matches = tuple(capability for capability in capabilities if capability.binding == "sync")
        if len(matches) != 1:
            raise RuntimeError("GGEN_SYNC_CAPABILITY_NOT_UNAMBIGUOUS")
        result = await self._runtime.act(
            ActuationIntent(
                episode_id=self._episode_id,
                capability=matches[0].iri,
                payload={"agent_id": spec.agent_id, "inputs": inputs},
                authority_ref=self._authority_ref,
                principal=self._principal,
                idempotency_key=digest(
                    {
                        "agent_id": spec.agent_id,
                        "pack_ref": spec.pack_ref,
                        "inputs": inputs,
                    }
                ),
            )
        )
        if not result.accepted:
            raise RuntimeError(result.receipt.reason or result.standing.value)
        observed = result.observation or await self._runtime.observe(self._episode_id)
        return {
            "accepted": True,
            "standing": result.standing.value,
            "receipt_id": result.receipt.receipt_id,
            "state": observed.state,
        }


def manufacture_ggen_agent_space(
    *,
    roles: tuple[str, ...],
    planners: tuple[str, ...],
    objectives: tuple[str, ...],
    observation_projections: tuple[str, ...],
    action_projections: tuple[str, ...],
    packs: tuple[str, ...],
    max_combinations: int = 10000,
) -> CombinationSpace:
    """Preserve the complete logical-agent DfCM cross product without selecting.

    Logical population cardinality may be enormous while active WIP remains
    independently bounded by each admitted ``GgenAgentSpec.max_wip``.
    """

    return manufacture_combination_space(
        (
            Factor(factor_id="role", alternatives=roles),
            Factor(factor_id="planner", alternatives=planners),
            Factor(factor_id="objective", alternatives=objectives),
            Factor(factor_id="observation_projection", alternatives=observation_projections),
            Factor(factor_id="action_projection", alternatives=action_projections),
            Factor(factor_id="pack", alternatives=packs),
        ),
        bounds=ExplorationBounds(max_combinations=max_combinations),
    )


def _project(value: Mapping[str, Any], keys: tuple[str, ...], *, kind: str) -> dict[str, Any]:
    if not keys:
        return dict(value)
    missing = tuple(key for key in keys if key not in value)
    if missing:
        raise ValueError(f"{kind}_PROJECTION_MISSING:{missing!r}")
    return {key: value[key] for key in keys}


class GgenAgentRuntime:
    """Bounded LLM-free runtime for a population of logical ggen agents.

    The runtime deliberately *refuses* an invocation once the spec's WIP
    limit is saturated.  Waiting work is inventory too; silently queuing it
    would defeat the Little's-Law control this abstraction exists to expose.
    """

    def __init__(
        self,
        specs: tuple[GgenAgentSpec, ...],
        manufacturer: GgenManufacturer,
    ) -> None:
        by_id = {spec.agent_id: spec for spec in specs}
        if len(by_id) != len(specs):
            raise ValueError("DUPLICATE_GGEN_AGENT_ID")
        self._specs = by_id
        self._manufacturer = manufacturer
        self._active = {agent_id: 0 for agent_id in by_id}
        self._lock = anyio.Lock()

    def specs(self) -> tuple[GgenAgentSpec, ...]:
        return tuple(self._specs[key] for key in sorted(self._specs))

    def wip(self) -> dict[str, int]:
        return dict(self._active)

    async def invoke(
        self,
        agent_id: str,
        *,
        observation: Mapping[str, Any],
        inputs: Mapping[str, Any] | None = None,
    ) -> GgenAgentResult:
        spec = self._specs.get(agent_id)
        if spec is None:
            raise KeyError(f"UNKNOWN_GGEN_AGENT:{agent_id}")

        async with self._lock:
            if self._active[agent_id] >= spec.max_wip:
                payload = {
                    "agent_id": agent_id,
                    "standing": Standing.REFUSED.value,
                    "reason": "LITTLES_LAW_WIP_LIMIT",
                    "active_wip": self._active[agent_id],
                    "max_wip": spec.max_wip,
                }
                return GgenAgentResult(
                    agent_id=agent_id,
                    standing=Standing.REFUSED,
                    reason="LITTLES_LAW_WIP_LIMIT",
                    manufacturer_ref=self._manufacturer.manufacturer_ref,
                    receipt_digest=digest(payload),
                )
            self._active[agent_id] += 1

        try:
            projected_observation = _project(
                observation,
                spec.observation_keys,
                kind="OBSERVATION",
            )
            produced = await self._manufacturer.manufacture(
                spec=spec,
                observation=projected_observation,
                inputs=dict(inputs or {}),
            )
            output = _project(produced, spec.output_keys, kind="ACTION")
            payload = {
                "agent_id": agent_id,
                "spec": spec.model_dump(mode="json"),
                "observation": projected_observation,
                "inputs": dict(inputs or {}),
                "output": output,
                "manufacturer_ref": self._manufacturer.manufacturer_ref,
                "llm_calls": 0,
            }
            return GgenAgentResult(
                agent_id=agent_id,
                standing=Standing.ALIVE,
                reason="DETERMINISTIC_MANUFACTURE_COMPLETE",
                output=output,
                manufacturer_ref=self._manufacturer.manufacturer_ref,
                receipt_digest=digest(payload),
            )
        except Exception as exc:
            payload = {
                "agent_id": agent_id,
                "type": type(exc).__name__,
                "message": str(exc),
            }
            return GgenAgentResult(
                agent_id=agent_id,
                standing=Standing.BLOCKED,
                reason=f"MANUFACTURE_BLOCKED:{type(exc).__name__}:{exc}",
                manufacturer_ref=self._manufacturer.manufacturer_ref,
                receipt_digest=digest(payload),
            )
        finally:
            async with self._lock:
                self._active[agent_id] -= 1
