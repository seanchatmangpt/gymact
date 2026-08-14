"""LLM-free logical agents backed by deterministic ggen manufacture.

An agent in this module is a projection, not a conversational process:

    Agent = Planner x Role x Objective x ObservationProjection x ActionProjection x Pack

The DfCM possibility space is preserved independently of active execution. A
``GgenAgentRuntime`` admits only a bounded amount of active work and refuses
excess WIP rather than hiding it in an internal queue. Agent specifications
may themselves be compiled from a ggen pack's RDF ABox, so the logical
organization is data rather than hand-written Python constructors.

No class in this module constructs, requires, or calls an LLM.

Naming/boundary note, recorded here per `.claude/rules/ontology.md`'s "Gap
documentation" convention rather than left implicit: `compile_ggen_agent_specs`
and `load_task_agent_assignments` below parse an RDF/Turtle graph via
`rdflib` at runtime, in the Python hot path, every time an agent runtime is
constructed -- no Rust/WASM artifact is produced anywhere in this module, and
no actual `ggen` (Rust manufacture) invocation occurs. `.claude/rules/
ggen-boundary.md` states ggen exists specifically to manufacture the Rust/WASM
side of GymAct "with no RDF engine in the hot path" -- this module's live,
per-call RDF parsing is not that. It is, however, a legitimate instance of
`.claude/rules/python-native.md`'s explicitly permitted pattern: "canonical
Pydantic models... dynamically built from SHACL/JSON Schema" -- the RDF graph
here plays the same role a JSON Schema would for `pydantic`'s own dynamic
model construction, just expressed in Turtle. The module and its owning
directory are named/located as if they were ggen artifacts (`ggen_agent.py`,
reading from `ggen/mna-gym-pack/`), which invites exactly the confusion the
boundary doc exists to prevent even though no mechanical rule is actually
violated. Kept as-is (real, tested, no functional issue) rather than reworked
as part of this merge; a future contributor should not have to re-derive this
distinction from scratch.
"""
from __future__ import annotations

import inspect
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any, Literal, Protocol, runtime_checkable

import anyio
from pydantic import Field
from rdflib import DCTERMS, RDF, Graph, Namespace

from gymact.combinatorial import (
    CombinationSpace,
    ExplorationBounds,
    Factor,
    manufacture_combination_space,
)
from gymact.evidence import digest
from gymact.models import ActuationIntent, FrozenModel, Standing

PROV = Namespace("http://www.w3.org/ns/prov#")
PPLAN = Namespace("http://purl.org/net/p-plan#")

_LOGICAL_AGENT_KIND = "logical-agent"
_OBSERVATION_PROJECTION_KIND = "observation-projection"
_ACTION_PROJECTION_KIND = "action-projection"
_GGEN_PACK_KIND = "ggen-pack"


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


def _local_name(value: Any) -> str:
    iri = str(value)
    for separator in ("#", ":"):
        if separator in iri:
            iri = iri.rsplit(separator, 1)[-1]
    return iri


def _load_pack_graph(pack_dir: Path) -> Graph:
    graph = Graph()
    flat = pack_dir / "ontology.ttl"
    if flat.is_file():
        graph.parse(flat, format="turtle")
    split_dir = pack_dir / "ontology"
    if split_dir.is_dir():
        for ttl_file in sorted(split_dir.glob("*.ttl")):
            graph.parse(ttl_file, format="turtle")
    return graph


def _exactly_one(values: tuple[Any, ...], *, field: str, subject: Any) -> Any:
    if len(values) != 1:
        raise ValueError(
            f"GGEN_AGENT_{field}_CARDINALITY:{subject}:{len(values)}"
        )
    return values[0]


def _objects(graph: Graph, subject: Any, predicate: Any) -> tuple[Any, ...]:
    return tuple(graph.objects(subject, predicate))


def _has_kind(graph: Graph, subject: Any, expected: str) -> bool:
    return any(
        _local_name(kind) == expected
        for kind in graph.objects(subject, DCTERMS.type)
    )


def _relation_of_kind(graph: Graph, subject: Any, expected: str) -> Any:
    matches = tuple(
        relation
        for relation in graph.objects(subject, DCTERMS.relation)
        if _has_kind(graph, relation, expected)
    )
    return _exactly_one(matches, field=expected.upper(), subject=subject)


def _projection_keys(graph: Graph, projection: Any) -> tuple[str, ...]:
    keys: list[str] = []
    for part in graph.objects(projection, DCTERMS.hasPart):
        identifier = _exactly_one(
            _objects(graph, part, DCTERMS.identifier),
            field="PROJECTION_KEY",
            subject=part,
        )
        keys.append(str(identifier))
    return tuple(sorted(keys))


def _qualified_agent_association(graph: Graph, agent: Any) -> Any:
    associations = tuple(
        association
        for association in graph.subjects(PROV.agent, agent)
        if (association, RDF.type, PROV.Association) in graph
    )
    association = _exactly_one(
        associations,
        field="ASSOCIATION",
        subject=agent,
    )
    activities = tuple(
        activity
        for activity in graph.subjects(PROV.qualifiedAssociation, association)
        if (activity, RDF.type, PROV.Activity) in graph
    )
    _exactly_one(
        activities,
        field="ASSOCIATION_ACTIVITY",
        subject=agent,
    )
    return association


def compile_ggen_agent_specs(pack_dir: Path) -> tuple[GgenAgentSpec, ...]:
    """Compile logical-agent specs from a public-ontology RDF ABox.

    Only public predicates/classes are structural. Domain distinctions such
    as ``logical-agent`` and ``action-projection`` remain SKOS concept data
    carried through ``dct:type``. Every field is cardinality checked and a
    malformed agent fails closed.
    """
    graph = _load_pack_graph(pack_dir)
    specs: list[GgenAgentSpec] = []

    for agent in sorted(graph.subjects(RDF.type, PROV.Agent), key=str):
        if not _has_kind(graph, agent, _LOGICAL_AGENT_KIND):
            continue

        agent_id = str(
            _exactly_one(
                _objects(graph, agent, DCTERMS.identifier),
                field="ID",
                subject=agent,
            )
        )
        association = _qualified_agent_association(graph, agent)
        role = _exactly_one(
            _objects(graph, association, PROV.hadRole),
            field="ROLE",
            subject=agent,
        )
        planner = _exactly_one(
            _objects(graph, association, PROV.hadPlan),
            field="PLANNER",
            subject=agent,
        )
        objective = _exactly_one(
            _objects(graph, agent, DCTERMS.subject),
            field="OBJECTIVE",
            subject=agent,
        )
        observation_projection = _relation_of_kind(
            graph,
            agent,
            _OBSERVATION_PROJECTION_KIND,
        )
        action_projection = _relation_of_kind(
            graph,
            agent,
            _ACTION_PROJECTION_KIND,
        )
        pack = _relation_of_kind(graph, agent, _GGEN_PACK_KIND)

        extent_values = _objects(graph, agent, DCTERMS.extent)
        if len(extent_values) > 1:
            raise ValueError(
                f"GGEN_AGENT_MAX_WIP_CARDINALITY:{agent}:{len(extent_values)}"
            )
        max_wip = int(extent_values[0]) if extent_values else 1

        specs.append(
            GgenAgentSpec(
                agent_id=agent_id,
                role_ref=str(role),
                planner_ref=str(planner),
                objective_ref=str(objective),
                observation_projection_ref=str(observation_projection),
                action_projection_ref=str(action_projection),
                pack_ref=str(pack),
                observation_keys=_projection_keys(
                    graph,
                    observation_projection,
                ),
                output_keys=_projection_keys(graph, action_projection),
                max_wip=max_wip,
                mcp_tool_name=agent_id.replace("-", "_"),
            )
        )

    return tuple(sorted(specs, key=lambda spec: spec.agent_id))


def load_task_agent_assignments(pack_dir: Path) -> dict[str, str]:
    """Compile p-plan task -> logical-agent assignment from ``dct:contributor``."""
    graph = _load_pack_graph(pack_dir)
    assignments: dict[str, str] = {}

    for task in graph.subjects(RDF.type, PPLAN.Plan):
        identifiers = _objects(graph, task, DCTERMS.identifier)
        if not identifiers:
            continue
        identifier = str(
            _exactly_one(
                identifiers,
                field="TASK_ID",
                subject=task,
            )
        )
        contributors = tuple(
            contributor
            for contributor in graph.objects(task, DCTERMS.contributor)
            if _has_kind(graph, contributor, _LOGICAL_AGENT_KIND)
        )
        agent = _exactly_one(
            contributors,
            field="TASK_AGENT",
            subject=task,
        )
        agent_id = str(
            _exactly_one(
                _objects(graph, agent, DCTERMS.identifier),
                field="TASK_AGENT_ID",
                subject=agent,
            )
        )
        assignments[identifier] = agent_id

    return dict(sorted(assignments.items()))


class CallableGgenManufacturer:
    """Adapter for deterministic Python/ggen-generated callables.

    The callable may be synchronous or asynchronous. It receives only the
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


class ProjectionGgenManufacturer:
    """Machine-speed manufacturer for graph-compiled projection agents.

    The ggen pack manufactures the agent's observation/action projection.
    Runtime execution projects explicitly supplied values into the declared
    output keys. Missing output material is refused; nothing is guessed,
    prompted, or completed by an LM.
    """

    manufacturer_ref = "urn:gymact:manufacturer:ggen-projection"

    async def manufacture(
        self,
        *,
        spec: GgenAgentSpec,
        observation: dict[str, Any],
        inputs: dict[str, Any],
    ) -> Mapping[str, Any]:
        del observation
        missing = tuple(key for key in spec.output_keys if key not in inputs)
        if missing:
            raise ValueError(f"GGEN_PROJECTION_INPUT_MISSING:{missing!r}")
        return {key: inputs[key] for key in spec.output_keys}


class GymActGgenManufacturer:
    """Adapter over an already-materialized GymAct ``ggen`` episode.

    This adapter does not shell out around GymAct. It invokes the provider's
    existing ``sync`` capability through ``GymAct.act``. Therefore a sealed
    ``ProductionGymAct`` still requires the normal BRCE execution-grant path;
    this adapter never bypasses authority, capability scope, idempotency,
    verification evidence, or receipts.
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
        matches = tuple(
            capability
            for capability in capabilities
            if capability.binding == "sync"
        )
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
            Factor(
                factor_id="observation_projection",
                alternatives=observation_projections,
            ),
            Factor(
                factor_id="action_projection",
                alternatives=action_projections,
            ),
            Factor(factor_id="pack", alternatives=packs),
        ),
        bounds=ExplorationBounds(max_combinations=max_combinations),
    )


def _project(
    value: Mapping[str, Any],
    keys: tuple[str, ...],
    *,
    kind: str,
) -> dict[str, Any]:
    if not keys:
        return dict(value)
    missing = tuple(key for key in keys if key not in value)
    if missing:
        raise ValueError(f"{kind}_PROJECTION_MISSING:{missing!r}")
    return {key: value[key] for key in keys}


class GgenAgentRuntime:
    """Bounded LLM-free runtime for a population of logical ggen agents.

    The runtime deliberately *refuses* an invocation once the spec's WIP
    limit is saturated. Waiting work is inventory too; silently queuing it
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
