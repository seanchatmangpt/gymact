"""Generic ontology-driven GymAct provider compiler.

Given a ggen pack directory (an `ontology.ttl` declaring `pplan:Plan` task
instances in the shape `gymact`'s own gym algebra already uses), this module
mechanically compiles a real, executable `EnvironmentProvider` from that
graph -- no per-domain Python required.

This is the actual product per this repo's own doctrine: GymAct should be a
generalized executable-world/consequence runtime, deriving as much of a
gym's topology as possible from an admitted ontology rather than
accumulating hand-coded domain adapters. `gymact.gyms.togaf` is the first
generated instance -- see that module for a ~10-line configuration, not a
hand-coded environment; see `docs/prd/v26.8.11-togaf-fortune5-adm-gym.md`'s
"Architecture correction" section for why this replaced an earlier,
hand-coded, per-phase approach.

Task shape consumed (already the real shape `ggen/togaf-gym-pack/
ontology.ttl`'s ten `pplan:Plan` instances use, unmodified by this module):

    <task> a pplan:Plan ;
        dct:identifier "<family-prefix>.<NN>.<slug>" ;   # sort key
        dct:subject <artifact-1>, <artifact-2>, ... ;      # effect(s)
        dct:type <task-family-concept> .                   # authority tier

Derivation rules, all from data already in the graph, nothing invented:

- **Precondition chain**: task N requires every earlier task's (sorted by
  the numeric segment of `dct:identifier`) declared subjects to already be
  established facts. Deliberately crude (a strictly earlier-tasks-complete
  chain, not a general DAG) -- real and checkable, not narrated; a future
  ontology with genuinely branching preconditions is representable without
  changing this module, since the check is against real established facts,
  not a hardcoded sequence.
- **Effect**: each task's DO capability establishes one of its declared
  `dct:subject` artifacts as a fact. Multi-valued `dct:subject` tasks take a
  `subject` payload parameter selecting which one -- the general form of
  what `togaf.py`'s M1 slice hand-coded specially for Requirements
  Management; here every multi-subject task gets it for free.
- **Authority tier**: whether a capability requires an elevated authority
  reference, versus a standard one, is caller-configured per `dct:type`
  family name (see `OntologyDrivenProvider`'s `elevated_task_families`) --
  enforced by `TieredAuthorityResolver`, injected the same way any
  `AuthorityResolver` is (`.claude/rules/actuation-authority.md`'s own
  boundary: the environment/provider never decides authority itself).
- **Reset/loop-back**: a task whose family is in `reset_task_families`,
  when actuated, additionally clears every fact belonging to tasks whose
  family is in `reset_target_families` -- the general form of "Phase H
  reopens Requirements Management," expressed as two family-name sets
  instead of TOGAF-specific code.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from rdflib import Graph, URIRef

from gymact.models import AuthorityDecision, AuthorityRequest, Capability, Consequence

_TASK_QUERY = """
PREFIX pplan: <http://purl.org/net/p-plan#>
PREFIX dct: <http://purl.org/dc/terms/>
SELECT ?task ?identifier ?type WHERE {
  ?task a pplan:Plan ;
        dct:identifier ?identifier ;
        dct:type ?type .
}
"""

_SUBJECT_QUERY = """
PREFIX dct: <http://purl.org/dc/terms/>
SELECT ?subject WHERE { ?task dct:subject ?subject . }
"""


def _local_name(iri: str) -> str:
    for sep in ("#", ":"):
        if sep in iri:
            return iri.rsplit(sep, 1)[-1]
    return iri


def _sort_key(identifier: str) -> tuple[int, str]:
    """Topological sort key: an identifier's numeric segment (e.g.
    `togaf.10.phase-a` -> `10`) IS the real precondition ordering
    `_preconditions_for` relies on. Identifiers with no numeric segment at
    all (e.g. bare `sosa:Procedure` tasks' plain `dct:identifier` values
    like "read"/"do" -- see `load_procedures`) carry no real ordering
    signal, so they all collapse to the SAME key `(0, "")` -- not a
    per-identifier fallback -- so that no spurious precondition ordering
    is invented between tasks whose real ontology facts state no order at
    all. Real numeric-identifier tasks never hit this branch."""
    for part in identifier.split("."):
        if part.isdigit():
            return (int(part), identifier)
    return (0, "")


@dataclass(frozen=True)
class OntologyTask:
    task_iri: str
    identifier: str
    subjects: tuple[str, ...]
    family: str


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


def load_tasks(pack_dir: Path) -> tuple[OntologyTask, ...]:
    """Extract every real `pplan:Plan` task from a pack's ontology, sorted by
    the numeric segment of its `dct:identifier`."""
    graph = _load_pack_graph(pack_dir)
    tasks: list[OntologyTask] = []
    for task, identifier, type_ in graph.query(_TASK_QUERY):
        subjects = tuple(
            sorted(
                str(subject)
                for (subject,) in graph.query(
                    _SUBJECT_QUERY, initBindings={"task": URIRef(str(task))}
                )
            )
        )
        tasks.append(
            OntologyTask(
                task_iri=str(task),
                identifier=str(identifier),
                subjects=subjects,
                family=_local_name(str(type_)),
            )
        )
    return tuple(sorted(tasks, key=lambda t: _sort_key(t.identifier)))


_PROCEDURE_QUERY = """
PREFIX sosa: <http://www.w3.org/ns/sosa/>
PREFIX dct: <http://purl.org/dc/terms/>
SELECT ?procedure ?identifier ?type WHERE {
  ?procedure a sosa:Procedure ;
             dct:identifier ?identifier ;
             dct:type ?type .
}
"""


def load_procedures(pack_dir: Path) -> tuple[OntologyTask, ...]:
    """Extract bare `sosa:Procedure` capabilities from a pack that has no
    `pplan:Plan` task wrapper at all (e.g. `protocol-gym-pack`'s real
    ontology.ttl: two `sosa:Procedure` capabilities, `dct:identifier`
    naming each, `dct:type` giving READ/DO consequence, no `dct:subject`
    artifact-establishment model whatsoever -- a genuinely different real
    shape from `load_tasks`'s `pplan:Plan` tasks, confirmed by direct read
    before writing this function, not assumed).

    Honest modeling choice, stated rather than papered over: a bare
    `sosa:Procedure` has no natural topological order (no numeric
    `dct:identifier` prefix the way `pplan:Plan` tasks have) and no
    `dct:subject` artifact to establish. This function therefore treats
    each procedure as establishing exactly one fact -- its own IRI -- with
    NO preconditions on any other procedure: `_sort_key` collapses every
    non-numeric identifier to the same key `(0, "")`, so
    `OntologyDrivenEnvironment._preconditions_for`'s strictly-earlier-tasks
    chain admits every bare-procedure task from the start -- there is no
    real, present ordering constraint in this pack's own facts, and
    inventing one (e.g. alphabetical) would misrepresent them.
    `family` is the `dct:type` object's local name (`read`/`do`), reusing
    the same authority-tier/reset-family mechanism `load_tasks`-derived
    tasks already use."""
    graph = _load_pack_graph(pack_dir)
    tasks: list[OntologyTask] = []
    for procedure, identifier, type_ in graph.query(_PROCEDURE_QUERY):
        tasks.append(
            OntologyTask(
                task_iri=str(procedure),
                identifier=str(identifier),
                subjects=(str(procedure),),
                family=_local_name(str(type_)),
            )
        )
    return tuple(sorted(tasks, key=lambda t: t.identifier))


def capability_iri(*, provider_name: str, task: OntologyTask) -> str:
    slug = task.identifier.replace(".", "-")
    return f"urn:gymact:{provider_name}:capability:{slug}"


def inspect_capability_iri(provider_name: str) -> str:
    return f"urn:gymact:{provider_name}:capability:inspect-state"


class OntologyDrivenEnvironment:
    """A real, fact-based world compiled from a pack's `pplan:Plan` tasks."""

    def __init__(
        self,
        *,
        provider_name: str,
        tasks: tuple[OntologyTask, ...],
        reset_task_families: frozenset[str],
        reset_target_families: frozenset[str],
        requires_authority: bool,
    ) -> None:
        self.environment_id = f"urn:gymact:{provider_name}:environment:{uuid4().hex}"
        self.requires_authority = requires_authority
        self._tasks = tasks
        self._reset_task_families = reset_task_families
        self._reset_target_families = reset_target_families
        self._state: set[str] = set()
        self._closed = False

        self._task_by_capability: dict[str, OntologyTask] = {
            capability_iri(provider_name=provider_name, task=task): task for task in tasks
        }
        inspect_iri = inspect_capability_iri(provider_name)
        self._capabilities = (
            Capability(
                iri=inspect_iri,
                title="Inspect world state",
                consequence=Consequence.READ,
                binding=inspect_iri,
            ),
            *(
                Capability(
                    iri=iri,
                    title=f"Execute {task.identifier}",
                    consequence=Consequence.DO,
                    binding=iri,
                )
                for iri, task in self._task_by_capability.items()
            ),
        )

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError("environment is torn down")

    def _all_subjects(self) -> frozenset[str]:
        return frozenset(subject for task in self._tasks for subject in task.subjects)

    def _preconditions_for(self, task: OntologyTask) -> frozenset[str]:
        return frozenset(
            subject
            for other in self._tasks
            if _sort_key(other.identifier) < _sort_key(task.identifier)
            for subject in other.subjects
        )

    def capabilities(self) -> tuple[Capability, ...]:
        self._ensure_open()
        return self._capabilities

    async def observe(self) -> dict[str, Any]:
        self._ensure_open()
        return {
            "facts": sorted(self._state),
            "goal_reached": self._all_subjects() <= self._state,
        }

    async def actuate(
        self, capability: Capability, payload: dict[str, Any]
    ) -> dict[str, Any]:
        self._ensure_open()
        task = self._task_by_capability.get(capability.binding)
        if task is None:
            raise ValueError("UNKNOWN_TASK_CAPABILITY")

        if not self._preconditions_for(task) <= self._state:
            raise ValueError("PRECONDITION_REFUSED")

        if len(task.subjects) == 1:
            subject = task.subjects[0]
        else:
            subject = payload.get("subject") if isinstance(payload, dict) else None
            if subject not in task.subjects:
                raise ValueError(f"UNKNOWN_SUBJECT:{subject!r}")

        if subject in self._state:
            raise ValueError("ALREADY_ESTABLISHED_REFUSED")

        before = sorted(self._state)
        self._state.add(subject)

        cleared: list[str] = []
        if task.family in self._reset_task_families:
            targets = frozenset(
                s
                for other in self._tasks
                if other.family in self._reset_target_families
                for s in other.subjects
            )
            to_clear = (targets & self._state) - {subject}
            cleared = sorted(to_clear)
            self._state -= to_clear

        return {
            "action": capability.binding,
            "established": subject,
            "cleared": cleared,
            "before_facts": before,
            "after_facts": sorted(self._state),
        }

    async def verify(self, expected: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
        self._ensure_open()
        observed = await self.observe()
        allowed = {"goal_reached"}
        unknown = set(expected) - allowed
        if unknown:
            raise ValueError(f"UNSUPPORTED_VERIFICATION:{sorted(unknown)!r}")
        passed = True
        if "goal_reached" in expected:
            if not isinstance(expected["goal_reached"], bool):
                raise TypeError("expected.goal_reached must be a boolean")
            passed = observed["goal_reached"] is expected["goal_reached"]
        return passed, observed

    async def checkpoint(self) -> dict[str, Any]:
        self._ensure_open()
        return {"facts": sorted(self._state)}

    async def restore(self, checkpoint: dict[str, Any]) -> None:
        self._ensure_open()
        facts = checkpoint.get("facts")
        if not isinstance(facts, list) or not all(isinstance(item, str) for item in facts):
            raise TypeError("checkpoint.facts must be a list of strings")
        self._state = set(facts)

    async def teardown(self) -> None:
        self._closed = True


class OntologyDrivenProvider:
    """Mechanically compiles an `EnvironmentProvider` from a pack's
    `pplan:Plan`-shaped `ontology.ttl`. See module docstring for the
    derivation rules."""

    materialization_requires_authority = False

    def __init__(
        self,
        *,
        name: str,
        pack_dir: Path,
        elevated_task_families: frozenset[str] = frozenset(),
        reset_task_families: frozenset[str] = frozenset(),
        reset_target_families: frozenset[str] = frozenset(),
    ) -> None:
        self.name = name
        self._pack_dir = pack_dir
        self.elevated_task_families = frozenset(elevated_task_families)
        self._reset_task_families = frozenset(reset_task_families)
        self._reset_target_families = frozenset(reset_target_families)

    def tasks(self) -> tuple[OntologyTask, ...]:
        return load_tasks(self._pack_dir)

    def elevated_capability_iris(self) -> frozenset[str]:
        """Capability IRIs whose task family is in `elevated_task_families` --
        the real input a `TieredAuthorityResolver` needs to enforce the
        authority separation this provider's tasks declare."""
        return frozenset(
            capability_iri(provider_name=self.name, task=task)
            for task in self.tasks()
            if task.family in self.elevated_task_families
        )

    async def materialize(
        self, *, scenario: str | None, config: dict[str, Any]
    ) -> OntologyDrivenEnvironment:
        del scenario
        requires_authority = config.get("requires_authority", True)
        if not isinstance(requires_authority, bool):
            raise TypeError("config.requires_authority must be a boolean")
        tasks = self.tasks()
        if not tasks:
            raise ValueError(f"NO_TASKS_FOUND_IN_PACK:{self._pack_dir}")
        return OntologyDrivenEnvironment(
            provider_name=self.name,
            tasks=tasks,
            reset_task_families=self._reset_task_families,
            reset_target_families=self._reset_target_families,
            requires_authority=requires_authority,
        )


_ODRL_PERMISSION_QUERY = """
PREFIX odrl: <http://www.w3.org/ns/odrl/2/>
SELECT ?permission ?target ?assigner ?assignee WHERE {
  { ?permission a odrl:Permission . }
  UNION
  { ?holder odrl:permission ?permission . ?permission a odrl:Permission . }
  OPTIONAL { ?permission odrl:target ?target . }
  OPTIONAL { ?permission odrl:assigner ?assigner . }
  OPTIONAL { ?permission odrl:assignee ?assignee . }
}
"""


@dataclass(frozen=True)
class OdrlPermission:
    permission_iri: str | None
    target: str | None
    assigner: str | None
    assignee: str | None


def load_odrl_permissions(pack_dir: Path) -> tuple[OdrlPermission, ...]:
    """Extract every real `odrl:Permission` fact from a pack's ontology --
    both bare (a subject directly typed `odrl:Permission`, e.g. `multicloud-
    gym-pack`'s IAM operations) and nested under an `odrl:Policy`/`odrl:Set`
    via `odrl:permission` (e.g. `career-gym-pack`'s consent policy,
    `togaf-gym-pack`'s governance permission). Confirmed against all three
    real shapes present in this repo's own packs before writing this query."""
    graph = _load_pack_graph(pack_dir)
    permissions: list[OdrlPermission] = []
    seen: set[str] = set()
    for row in graph.query(_ODRL_PERMISSION_QUERY):
        permission_iri = str(row.permission) if row.permission is not None else None
        key = permission_iri or f"blank:{len(permissions)}"
        if key in seen:
            continue
        seen.add(key)
        permissions.append(
            OdrlPermission(
                permission_iri=permission_iri,
                target=str(row.target) if row.target is not None else None,
                assigner=str(row.assigner) if row.assigner is not None else None,
                assignee=str(row.assignee) if row.assignee is not None else None,
            )
        )
    return tuple(permissions)


class OdrlAuthorityResolver:
    """Authority decisions driven by real, already-declared `odrl:Permission`
    facts in a pack's ontology -- not Python-side configuration
    (`TieredAuthorityResolver`'s family-name sets), not newly-constructed
    ODRL instances. Reads data this repo's own packs already admit.

    Honest, real scope (three shapes found across this repo's packs, not
    every conceivable ODRL pattern):

    - A permission with a real `odrl:assigner`: admits a request only when
      `request.authority_ref` equals that assigner's IRI verbatim -- the
      caller must present the identity ODRL names as authorized to grant
      this permission (`togaf-gym-pack`'s real governance permission has
      `odrl:assigner <urn:gymact:togaf:org:architecture-board>`).
    - A permission with a real `odrl:target` matching `request.capability_ref`
      and no assigner: admits any request carrying a non-`None`
      `authority_ref` (`career-gym-pack`'s consent policy has no assigner --
      the permission's mere existence for this exact target is the grant).
    - A capability IRI itself directly typed `odrl:Permission` (no separate
      `odrl:target`, `multicloud-gym-pack`'s real shape): the same
      any-non-`None`-ref admission as above, matched by `permission_iri`
      instead of `target`.

    No permission at all matching `request.capability_ref` -> refused with
    `ODRL_NO_PERMISSION_FOR_CAPABILITY`, regardless of ref."""

    def __init__(self, permissions: tuple[OdrlPermission, ...]) -> None:
        self._permissions = permissions

    async def authorize(self, request: AuthorityRequest) -> AuthorityDecision:
        ref = request.authority_ref
        matching = [
            p
            for p in self._permissions
            if p.target == request.capability_ref
            or p.permission_iri == request.capability_ref
        ]
        if not matching:
            return AuthorityDecision(
                admitted=False, reason="ODRL_NO_PERMISSION_FOR_CAPABILITY"
            )
        if ref is None:
            return AuthorityDecision(admitted=False, reason="LIVE_AUTHORITY_REQUIRED")
        assigners = {p.assigner for p in matching if p.assigner is not None}
        if assigners:
            if ref not in assigners:
                return AuthorityDecision(
                    admitted=False, reason="ODRL_ASSIGNER_MISMATCH"
                )
            return AuthorityDecision(
                admitted=True,
                reason="ODRL_ASSIGNER_ADMITTED",
                evidence_ref=f"urn:gymact:authority-decision:odrl:{ref}",
            )
        return AuthorityDecision(
            admitted=True,
            reason="ODRL_PERMISSION_ADMITTED",
            evidence_ref=f"urn:gymact:authority-decision:odrl:{ref}",
        )


class TieredAuthorityResolver:
    """Admits `elevated_ref` for any capability, and `standard_ref` only for
    capabilities outside `elevated_capabilities`. Generic, real authority-
    tier enforcement for `OntologyDrivenProvider`-compiled gyms -- the
    provider/environment never decides authority itself
    (`.claude/rules/actuation-authority.md`); this resolver is the injected
    policy decision point that does."""

    def __init__(
        self,
        *,
        elevated_capabilities: frozenset[str],
        standard_ref: str,
        elevated_ref: str,
    ) -> None:
        self._elevated_capabilities = elevated_capabilities
        self._standard_ref = standard_ref
        self._elevated_ref = elevated_ref

    async def authorize(self, request: AuthorityRequest) -> AuthorityDecision:
        ref = request.authority_ref
        if ref is None:
            return AuthorityDecision(admitted=False, reason="LIVE_AUTHORITY_REQUIRED")
        if request.capability_ref in self._elevated_capabilities:
            admitted = ref == self._elevated_ref
        else:
            admitted = ref in (self._standard_ref, self._elevated_ref)
        if not admitted:
            return AuthorityDecision(admitted=False, reason="AUTHORITY_NOT_ADMITTED")
        return AuthorityDecision(
            admitted=True,
            reason="AUTHORITY_ADMITTED",
            evidence_ref=f"urn:gymact:authority-decision:{ref}",
        )
