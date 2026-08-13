"""Public-semantic dependency-world execution kernel.

This module is domain-neutral. It consumes an admitted RDF ABox and turns
PROV/DCTERMS dependency facts, SOSA procedures, ODRL actor permissions, and
DQV bounds into one deterministic bounded Environment.

It deliberately does *not* perform authority decisions: GymAct's injected
AuthorityResolver remains the only permission boundary for DO. It also has
no network/process/shell primitive. A procedure can only change the direct
status of an asset already present in the admitted graph; dependency effects
are recomputed transactionally and refused before commit if configured bounds
would be exceeded.
"""

from __future__ import annotations

from collections import deque
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from rdflib import Graph, Literal, Namespace, RDF, URIRef

from gymact.models import Capability, Consequence

DCT = Namespace("http://purl.org/dc/terms/")
PROV = Namespace("http://www.w3.org/ns/prov#")
SOSA = Namespace("http://www.w3.org/ns/sosa/")
ODRL = Namespace("http://www.w3.org/ns/odrl/2/")
DQV = Namespace("http://www.w3.org/ns/dqv#")
SKOS = Namespace("http://www.w3.org/2004/02/skos/core#")


def _one(graph: Graph, subject: URIRef, predicate: URIRef, *, label: str) -> object:
    values = tuple(graph.objects(subject, predicate))
    if len(values) != 1:
        raise ValueError(f"{label}_CARDINALITY:{subject}:{len(values)}")
    return values[0]


def _notation(graph: Graph, concept: object) -> str:
    if not isinstance(concept, URIRef):
        raise ValueError(f"CONCEPT_NOT_IRI:{concept!r}")
    return str(_one(graph, concept, SKOS.notation, label="SKOS_NOTATION"))


@dataclass(frozen=True, slots=True)
class DependencyAsset:
    iri: str
    identifier: str
    title: str
    domain: str
    requires: tuple[str, ...]
    initial_status: str


@dataclass(frozen=True, slots=True)
class DependencyCapability:
    iri: str
    identifier: str
    title: str
    family: str
    effect_status: str
    synthetic_only: bool

    def runtime(self) -> Capability:
        return Capability(
            iri=self.iri,
            title=self.title,
            consequence=Consequence.DO,
            binding=self.identifier,
        )


@dataclass(frozen=True, slots=True)
class DependencyWorldCatalog:
    assets: tuple[DependencyAsset, ...]
    capabilities: tuple[DependencyCapability, ...]
    actor_actions: dict[str, tuple[str, ...]]
    actor_visibility: dict[str, tuple[str, ...]]
    actor_lag_steps: dict[str, int]
    max_depth: int
    max_events: int
    max_impacted_resources: int

    @classmethod
    def from_graph(cls, graph: Graph, *, local_prefix: str) -> "DependencyWorldCatalog":
        assets: list[DependencyAsset] = []
        asset_by_iri: dict[str, str] = {}
        for asset in sorted(
            {s for s in graph.subjects(RDF.type, PROV.Entity) if (s, RDF.type, SOSA.FeatureOfInterest) in graph},
            key=str,
        ):
            assert isinstance(asset, URIRef)
            identifier = str(_one(graph, asset, DCT.identifier, label="ASSET_IDENTIFIER"))
            title = str(_one(graph, asset, DCT.title, label="ASSET_TITLE"))
            domain = _notation(graph, _one(graph, asset, DCT.type, label="ASSET_DOMAIN"))
            requires = tuple(sorted(str(item) for item in graph.objects(asset, DCT.requires)))
            results = {
                str(result)
                for obs in graph.subjects(SOSA.hasFeatureOfInterest, asset)
                if (obs, RDF.type, SOSA.Observation) in graph
                for result in graph.objects(obs, SOSA.hasResult)
            }
            if len(results) != 1:
                raise ValueError(f"INITIAL_STATUS_CARDINALITY:{asset}:{len(results)}")
            status = _notation(graph, URIRef(next(iter(results))))
            asset_by_iri[str(asset)] = identifier
            assets.append(
                DependencyAsset(
                    iri=str(asset),
                    identifier=identifier,
                    title=title,
                    domain=domain,
                    requires=requires,
                    initial_status=status,
                )
            )

        known_asset_iris = set(asset_by_iri)
        for asset in assets:
            unknown = set(asset.requires) - known_asset_iris
            if unknown:
                raise ValueError(f"UNKNOWN_DEPENDENCY:{asset.identifier}:{sorted(unknown)!r}")

        capabilities: list[DependencyCapability] = []
        cap_by_iri: dict[str, DependencyCapability] = {}
        synthetic_profile = URIRef(f"{local_prefix}profile:synthetic-only")
        for cap in sorted(set(graph.subjects(RDF.type, SOSA.Procedure)), key=str):
            assert isinstance(cap, URIRef)
            identifier = str(_one(graph, cap, DCT.identifier, label="CAPABILITY_IDENTIFIER"))
            title = str(_one(graph, cap, DCT.title, label="CAPABILITY_TITLE"))
            family = _notation(graph, _one(graph, cap, DCT.type, label="CAPABILITY_FAMILY"))
            effect_status = _notation(graph, _one(graph, cap, DCT.subject, label="CAPABILITY_EFFECT"))
            access = _notation(graph, _one(graph, cap, DCT.accessRights, label="CAPABILITY_CONSEQUENCE"))
            if access.upper() != "DO":
                raise ValueError(f"UNSUPPORTED_CAPABILITY_CONSEQUENCE:{identifier}:{access}")
            synthetic_only = (cap, DCT.conformsTo, synthetic_profile) in graph
            if family in {"disturbance", "environmental"} and not synthetic_only:
                raise ValueError(f"UNBOUNDED_DISTURBANCE_REFUSED:{identifier}")
            spec = DependencyCapability(
                iri=str(cap),
                identifier=identifier,
                title=title,
                family=family,
                effect_status=effect_status,
                synthetic_only=synthetic_only,
            )
            capabilities.append(spec)
            cap_by_iri[str(cap)] = spec

        actor_actions: dict[str, tuple[str, ...]] = {}
        actor_visibility: dict[str, tuple[str, ...]] = {}
        actors = sorted(set(graph.subjects(RDF.type, PROV.Agent)), key=str)
        for actor in actors:
            actor_id = str(_one(graph, actor, DCT.identifier, label="ACTOR_IDENTIFIER"))
            actions: set[str] = set()
            visible: set[str] = set()
            for permission in graph.subjects(ODRL.assignee, actor):
                if (permission, RDF.type, ODRL.Permission) not in graph:
                    continue
                for action in graph.objects(permission, ODRL.action):
                    if action == ODRL.read:
                        visible.update(
                            asset_by_iri[str(target)]
                            for target in graph.objects(permission, ODRL.target)
                            if str(target) in asset_by_iri
                        )
                    elif str(action) in cap_by_iri:
                        actions.add(str(action))
            actor_actions[actor_id] = tuple(sorted(actions))
            actor_visibility[actor_id] = tuple(sorted(visible))

        def metric(metric_suffix: str, *, computed_on: URIRef | None = None) -> int:
            metric_iri = URIRef(f"{local_prefix}metric:{metric_suffix}")
            values: list[int] = []
            for measurement in graph.subjects(DQV.isMeasurementOf, metric_iri):
                if computed_on is not None and (measurement, DQV.computedOn, computed_on) not in graph:
                    continue
                raw = _one(graph, measurement, DQV.value, label="DQV_VALUE")
                values.append(int(raw.toPython() if isinstance(raw, Literal) else str(raw)))
            if len(values) != 1 or values[0] < 0:
                raise ValueError(f"METRIC_CARDINALITY_OR_VALUE:{metric_suffix}:{values!r}")
            return values[0]

        lag: dict[str, int] = {}
        for actor in actors:
            actor_id = str(_one(graph, actor, DCT.identifier, label="ACTOR_IDENTIFIER"))
            lag[actor_id] = metric("observation-lag-steps", computed_on=actor)

        return cls(
            assets=tuple(sorted(assets, key=lambda item: item.identifier)),
            capabilities=tuple(sorted(capabilities, key=lambda item: item.identifier)),
            actor_actions=actor_actions,
            actor_visibility=actor_visibility,
            actor_lag_steps=lag,
            max_depth=metric("max-depth"),
            max_events=metric("max-events"),
            max_impacted_resources=metric("max-impacted-resources"),
        )


class DependencyWorldEnvironment:
    """Transactional graph world with actor-scoped observation and DO surfaces."""

    def __init__(self, *, provider_name: str, catalog: DependencyWorldCatalog, actor: str, requires_authority: bool) -> None:
        if actor not in catalog.actor_actions:
            raise ValueError(f"UNKNOWN_ACTOR:{actor}")
        self.environment_id = f"urn:gymact:{provider_name}:environment:{uuid4().hex}"
        self.requires_authority = requires_authority
        self.actor = actor
        self._catalog = catalog
        self._closed = False
        self._assets = {asset.identifier: asset for asset in catalog.assets}
        self._iri_to_id = {asset.iri: asset.identifier for asset in catalog.assets}
        self._cap_specs = {cap.iri: cap for cap in catalog.capabilities}
        self._allowed_caps = frozenset(catalog.actor_actions[actor])
        self._visible = frozenset(catalog.actor_visibility[actor])
        self._dependencies = {
            asset.identifier: tuple(self._iri_to_id[item] for item in asset.requires)
            for asset in catalog.assets
        }
        reverse: dict[str, set[str]] = {key: set() for key in self._assets}
        for source, required in self._dependencies.items():
            for target in required:
                reverse[target].add(source)
        self._reverse = {key: tuple(sorted(value)) for key, value in reverse.items()}
        self._direct = {asset.identifier: asset.initial_status for asset in catalog.assets}
        self._effective = dict(self._direct)
        self._step = 0
        self._history: list[dict[str, str]] = [deepcopy(self._effective)]

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError("environment is torn down")

    def capabilities(self) -> tuple[Capability, ...]:
        self._ensure_open()
        return tuple(cap.runtime() for cap in self._catalog.capabilities if cap.iri in self._allowed_caps)

    async def observe(self) -> dict[str, Any]:
        """Independent read from committed history, never an actuator echo."""
        self._ensure_open()
        lag = self._catalog.actor_lag_steps[self.actor]
        observed_step = max(0, self._step - lag)
        snapshot = self._history[observed_step]
        return {
            "actor": self.actor,
            "world_step": self._step,
            "observed_step": observed_step,
            "staleness_steps": self._step - observed_step,
            "assets": {key: snapshot[key] for key in sorted(self._visible)},
        }

    def _desired_status(self, asset_id: str, *, direct: dict[str, str], effective: dict[str, str]) -> str:
        own = direct[asset_id]
        if own != "healthy":
            return own
        if any(effective[dep] != "healthy" for dep in self._dependencies[asset_id]):
            return "degraded"
        return "healthy"

    def _simulate(self, *, target: str, effect_status: str) -> tuple[dict[str, str], dict[str, str], tuple[str, ...]]:
        direct = dict(self._direct)
        effective = dict(self._effective)
        direct[target] = effect_status
        queue: deque[tuple[str, int]] = deque([(target, 0)])
        changed: set[str] = set()
        events = 0
        seen_depth: dict[str, int] = {target: 0}
        while queue:
            current, depth = queue.popleft()
            desired = self._desired_status(current, direct=direct, effective=effective)
            if effective[current] != desired:
                effective[current] = desired
                changed.add(current)
                events += 1
                if events > self._catalog.max_events:
                    raise ValueError("PROPAGATION_MAX_EVENTS_REFUSED")
                if len(changed) > self._catalog.max_impacted_resources:
                    raise ValueError("PROPAGATION_MAX_IMPACT_REFUSED")
            for dependent in self._reverse[current]:
                next_depth = depth + 1
                if next_depth > self._catalog.max_depth:
                    raise ValueError("PROPAGATION_MAX_DEPTH_REFUSED")
                prior = seen_depth.get(dependent)
                if prior is None or next_depth < prior:
                    seen_depth[dependent] = next_depth
                    queue.append((dependent, next_depth))
        return direct, effective, tuple(sorted(changed))

    async def actuate(self, capability: Capability, payload: dict[str, Any]) -> dict[str, Any]:
        self._ensure_open()
        spec = self._cap_specs.get(capability.iri)
        if spec is None or spec.iri not in self._allowed_caps:
            raise ValueError("CAPABILITY_NOT_ADMITTED_FOR_ACTOR")
        if capability.binding != spec.identifier:
            raise ValueError("CAPABILITY_BINDING_DRIFT")
        target = payload.get("target") if isinstance(payload, dict) else None
        if not isinstance(target, str) or target not in self._assets:
            raise ValueError("TARGET_OUTSIDE_MATERIALIZED_WORLD_REFUSED")
        if spec.family in {"disturbance", "environmental"} and not spec.synthetic_only:
            raise ValueError("NON_SYNTHETIC_DISTURBANCE_REFUSED")
        direct, effective, changed = self._simulate(target=target, effect_status=spec.effect_status)
        before_step = self._step
        self._direct = direct
        self._effective = effective
        self._step += 1
        self._history.append(deepcopy(self._effective))
        return {
            "procedure": spec.identifier,
            "target": target,
            "direct_effect": spec.effect_status,
            "changed_assets": list(changed),
            "before_step": before_step,
            "after_step": self._step,
            "synthetic_only": spec.synthetic_only,
        }

    async def verify(self, expected: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
        self._ensure_open()
        observed = await self.observe()
        expected_assets = expected.get("assets", {})
        if not isinstance(expected_assets, dict):
            raise TypeError("expected.assets must be an object")
        unknown = set(expected) - {"assets", "world_step", "observed_step", "staleness_steps", "actor"}
        if unknown:
            raise ValueError(f"UNSUPPORTED_VERIFICATION:{sorted(unknown)!r}")
        passed = all(observed.get(key) == value for key, value in expected.items() if key != "assets")
        passed = passed and all(observed["assets"].get(key) == value for key, value in expected_assets.items())
        return passed, observed

    async def checkpoint(self) -> dict[str, Any]:
        self._ensure_open()
        return {
            "actor": self.actor,
            "step": self._step,
            "direct": deepcopy(self._direct),
            "effective": deepcopy(self._effective),
            "history": deepcopy(self._history),
        }

    async def restore(self, checkpoint: dict[str, Any]) -> None:
        self._ensure_open()
        if checkpoint.get("actor") != self.actor:
            raise ValueError("CHECKPOINT_ACTOR_MISMATCH")
        direct = checkpoint.get("direct")
        effective = checkpoint.get("effective")
        history = checkpoint.get("history")
        step = checkpoint.get("step")
        if not isinstance(direct, dict) or set(direct) != set(self._assets):
            raise ValueError("CHECKPOINT_DIRECT_STATE_INVALID")
        if not isinstance(effective, dict) or set(effective) != set(self._assets):
            raise ValueError("CHECKPOINT_EFFECTIVE_STATE_INVALID")
        if not isinstance(history, list) or not history:
            raise ValueError("CHECKPOINT_HISTORY_INVALID")
        if not isinstance(step, int) or step < 0 or step >= len(history):
            raise ValueError("CHECKPOINT_STEP_INVALID")
        self._direct = deepcopy(direct)
        self._effective = deepcopy(effective)
        self._history = deepcopy(history[: step + 1])
        self._step = step

    async def teardown(self) -> None:
        self._closed = True


class DependencyWorldProvider:
    """Compile a bounded dependency world directly from one canonical RDF pack."""

    materialization_requires_authority = False

    def __init__(self, *, name: str, pack_dir: Path, local_prefix: str) -> None:
        self.name = name
        self.pack_dir = pack_dir
        self.local_prefix = local_prefix

    def graph(self) -> Graph:
        path = self.pack_dir / "ontology.ttl"
        if not path.is_file():
            raise FileNotFoundError(path)
        return Graph().parse(path, format="turtle")

    def catalog(self) -> DependencyWorldCatalog:
        return DependencyWorldCatalog.from_graph(self.graph(), local_prefix=self.local_prefix)

    async def materialize(self, *, scenario: str | None, config: dict[str, Any]) -> DependencyWorldEnvironment:
        del scenario
        actor = config.get("actor", "blue")
        if not isinstance(actor, str):
            raise TypeError("config.actor must be a string")
        requires_authority = config.get("requires_authority", True)
        if not isinstance(requires_authority, bool):
            raise TypeError("config.requires_authority must be a boolean")
        return DependencyWorldEnvironment(
            provider_name=self.name,
            catalog=self.catalog(),
            actor=actor,
            requires_authority=requires_authority,
        )
