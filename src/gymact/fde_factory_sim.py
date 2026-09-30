"""Deterministic, model-free, human-free simulation of the FDE factory loop.

Question answered: does `explore -> falsify -> admit -> compile -> exploit` make a stream of
engagements cheaper once a problem class is solved, and does it fail closed where the
consequence law says it must?  Zero LLM calls, zero human input: every "cognition" step is a
bounded, seeded enumeration over a finite disposition space inside a pure in-memory world.

Reuse (`.claude/rules/composition-admission.md`): this module adds no provider, transport, or
ontology term.  It composes existing primitives only --
`gymact.compileout` (recipe compile/admit), `gymact.authority` (fail-closed resolver) and
`gymact.evidence.digest` (content identity).  Public-vocabulary search for a new TBox was not
needed: nothing here is serialized as RDF.

Standing, stated honestly: the result is a SIMULATION of the mechanism.  The report carries
`origin="SIMULATED"`, `observed_execution=False`, and never a Western Digital / Sony
`ALIVE` claim -- see `.claude/rules/ocel-standing.md` and `ggen-boundary.md`.

Cost is reported per unit (`cognition_evals`, `verify_evals`, `lookups`) and is never converted
between units (`gymact.cost_ledger`: no manufactured exchange rate).
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field

from gymact.authority import AllowListAuthorityResolver, AuthorityResolver, DenyAuthorityResolver
from gymact.compileout import (
    CompiledRecipe,
    RecipeCache,
    RecipeIdentity,
    admit_compiled_recipe,
    compile_recipe,
)
from gymact.evidence import digest
from gymact.models import AuthorityRequest, FrozenModel, Operation, Standing

SIM_AUTHORITY_REF = "urn:gymact:sim:authority"
_VERIFIER_REF = "urn:gymact:sim:world-oracle"
_ACTION_REF = "urn:gymact:sim:apply-disposition"
_LOOKALIKES = 3
_COMMON_INSTANCES = 3
_RARE_INSTANCES = 3


class Path(StrEnum):
    EXPLORE = "EXPLORE"
    EXPLOIT = "EXPLOIT"
    REFUSED_AUTHORITY = "REFUSED_AUTHORITY"


class ExploreReason(StrEnum):
    FIRST_SOLVE = "FIRST_SOLVE"
    IDENTITY_DRIFT = "IDENTITY_DRIFT"
    VERIFY_DIVERGENCE = "VERIFY_DIVERGENCE"
    NO_COMPOUNDING = "NO_COMPOUNDING"


class DriftEvent(FrozenModel):
    """The world's truth for one class changes at `at_engagement` (before it runs).

    `announced=True` bumps the observable policy revision (new evidence is visible);
    `announced=False` is silent drift that only independent verification can catch.
    """

    at_engagement: int = Field(ge=1)
    class_id: str
    announced: bool


class SimulationSpec(FrozenModel):
    seed: int = 20260930
    n_classes: int = Field(default=6, ge=1)
    n_engagements: int = Field(default=60, ge=1)
    n_dispositions: int = Field(default=48, ge=_LOOKALIKES + 2)
    drift_events: tuple[DriftEvent, ...] = ()
    authority_granted: bool = True


class EngagementRecord(FrozenModel):
    index: int
    class_id: str
    path: Path
    explore_reason: ExploreReason | None = None
    cognition_evals: int = 0
    verify_evals: int = 0
    lookups: int = 0
    verified: bool = False
    standing: Standing
    reason: str


class ClassCurve(FrozenModel):
    class_id: str
    cognition_evals_per_engagement: tuple[int, ...]
    first_admitted_at: int | None
    verified_reuses: int


class ArmResult(FrozenModel):
    arm: str
    records: tuple[EngagementRecord, ...]
    curves: tuple[ClassCurve, ...]
    cognition_evals: int
    verify_evals: int
    lookups: int
    redundant_explorations: int
    unverified_consequences: int
    mu_size_by_engagement: tuple[int, ...]
    trace_digest: str


class SimulationReport(FrozenModel):
    origin: str = "SIMULATED"
    observed_execution: bool = False
    llm_calls: int = 0
    human_interactions: int = 0
    spec_digest: str
    seed: int
    factory: ArmResult
    baseline: ArmResult
    report_digest: str


def _rank(seed: int, *parts: object) -> str:
    return digest([seed, *parts])


class World:
    """Pure seeded world: per-class hidden truth that may drift by epoch."""

    def __init__(self, spec: SimulationSpec) -> None:
        self._spec = spec
        self._epoch: dict[str, int] = {}
        self._orders: dict[tuple[str, int], list[str]] = {}
        self._explore_orders: dict[str, list[str]] = {}

    def epoch(self, class_id: str) -> int:
        return self._epoch.get(class_id, 0)

    def drift(self, class_id: str) -> None:
        self._epoch[class_id] = self.epoch(class_id) + 1

    def _order(self, class_id: str, epoch: int) -> list[str]:
        """Truth-first ranking; pure in (seed, class, epoch), so memoized."""
        key = (class_id, epoch)
        if key not in self._orders:
            names = [f"disp-{i:02d}" for i in range(self._spec.n_dispositions)]
            self._orders[key] = sorted(
                names, key=lambda n: _rank(self._spec.seed, "truth", class_id, epoch, n)
            )
        return self._orders[key]

    def explore_order(self, class_id: str) -> list[str]:
        """Enumeration order the explorer uses; it never sees the truth ranking."""
        if class_id not in self._explore_orders:
            names = [f"disp-{i:02d}" for i in range(self._spec.n_dispositions)]
            self._explore_orders[class_id] = sorted(
                names, key=lambda n: _rank(self._spec.seed, "explore", class_id, n)
            )
        return self._explore_orders[class_id]

    def truth(self, class_id: str) -> str:
        return self._order(class_id, self.epoch(class_id))[0]

    def evaluate(self, class_id: str, candidate: str, kind: str, n: int) -> tuple[bool, str]:
        """Independent verdict plus a witnessed evaluation receipt ref."""
        order = self._order(class_id, self.epoch(class_id))
        ok = candidate == order[0] or (kind == "common" and candidate in order[1 : 1 + _LOOKALIKES])
        ref = "urn:gymact:sim:eval:" + digest(
            [class_id, self.epoch(class_id), candidate, kind, n, ok]
        )
        return ok, ref


def _identity(spec: SimulationSpec, class_id: str, revision: int, granted: bool) -> RecipeIdentity:
    return RecipeIdentity(
        problem_identity=class_id,
        environment_identity="urn:gymact:sim:world:" + _rank(spec.seed, "env")[:12],
        authority_class="allowlist" if granted else "deny",
        policy_revision=f"rev-{revision}",
        verifier_ref=_VERIFIER_REF,
        action_ref=_ACTION_REF,
        input_contract_digest=digest([_COMMON_INSTANCES, _RARE_INSTANCES]),
    )


def _authorize(resolver: AuthorityResolver, class_id: str, candidate: str) -> bool:
    """Drive the resolver's coroutine without an event loop (no sockets, no I/O).

    Sim resolvers are pure; one that suspends would need real I/O, which this sealed
    simulation refuses rather than silently awaiting.
    """
    coro = resolver.authorize(
        AuthorityRequest(
            episode_id="urn:gymact:sim:episode",
            subject_ref=f"urn:gymact:sim:class:{class_id}",
            operation=Operation.ACT,
            capability_ref=_ACTION_REF,
            payload={"disposition": candidate},
            authority_ref=SIM_AUTHORITY_REF,
        )
    )
    try:
        coro.send(None)
    except StopIteration as done:
        return bool(done.value.admitted)
    coro.close()
    raise RuntimeError("SIM_AUTHORITY_RESOLVER_SUSPENDED")


def _explore(world: World, class_id: str) -> tuple[str, tuple[str, ...], int]:
    """Bounded enumeration + independent challenge. Returns (survivor, receipts, evals)."""
    evals = 0
    for cand in world.explore_order(class_id):
        receipts: list[str] = []
        survived = True
        for kind, count in (("common", _COMMON_INSTANCES), ("rare", _RARE_INSTANCES)):
            for n in range(count):
                ok, ref = world.evaluate(class_id, cand, kind, n)
                evals += 1
                receipts.append(ref)
                if not ok:
                    survived = False
                    break
            if not survived:
                break
        if survived:
            return cand, tuple(receipts), evals
    raise RuntimeError("SIM_EXPLORATION_EXHAUSTED")  # unreachable: truth is always enumerable


def simulate(spec: SimulationSpec, *, arm: str) -> ArmResult:
    """Run one arm: `factory` (compile + reuse) or `baseline` (re-derive every time)."""
    if arm not in {"factory", "baseline"}:
        raise ValueError("SIM_UNKNOWN_ARM")
    factory = arm == "factory"
    world = World(spec)
    resolver: AuthorityResolver = (
        AllowListAuthorityResolver({SIM_AUTHORITY_REF})
        if spec.authority_granted
        else DenyAuthorityResolver()
    )
    classes = [f"class-{i:02d}" for i in range(spec.n_classes)]
    revision = dict.fromkeys(classes, 0)
    cache = RecipeCache()
    index: dict[str, str] = {}
    explored_identity: dict[str, tuple[int, int]] = {}  # class -> (revision, epoch) last solved
    records: list[EngagementRecord] = []
    mu_sizes: list[int] = []
    redundant = 0
    unverified = 0

    for i in range(1, spec.n_engagements + 1):
        for ev in spec.drift_events:
            if ev.at_engagement == i:
                world.drift(ev.class_id)
                if ev.announced:
                    revision[ev.class_id] += 1
        cid = classes[int(_rank(spec.seed, "stream", i), 16) % len(classes)]
        current = _identity(spec, cid, revision[cid], spec.authority_granted)
        lookups = 1
        reason: ExploreReason | None = ExploreReason.NO_COMPOUNDING
        recipe: CompiledRecipe | None = None

        if factory:
            reason = ExploreReason.FIRST_SOLVE
            found = index.get(cid)
            recipe = cache.get(found) if found else None
            if recipe is not None:
                admission = admit_compiled_recipe(recipe, current)
                if admission.admitted:
                    reason = None
                else:
                    reason = ExploreReason.IDENTITY_DRIFT
                    recipe = None

        if recipe is not None:  # EXPLOIT candidate: authority, then independent verify
            cand = recipe.candidate_ref
            if not _authorize(resolver, cid, cand):
                records.append(
                    EngagementRecord(
                        index=i,
                        class_id=cid,
                        path=Path.REFUSED_AUTHORITY,
                        lookups=lookups,
                        standing=Standing.REFUSED,
                        reason="AUTHORITY_NOT_ADMITTED_NO_CONSEQUENCE",
                    )
                )
                mu_sizes.append(len(index))
                continue
            ok, _ = world.evaluate(cid, cand, "rare", 0)
            if ok:
                records.append(
                    EngagementRecord(
                        index=i,
                        class_id=cid,
                        path=Path.EXPLOIT,
                        lookups=lookups,
                        verify_evals=1,
                        verified=True,
                        standing=Standing.CANDIDATE,
                        reason="COMPILED_RECIPE_VERIFIED_INDEPENDENTLY",
                    )
                )
                mu_sizes.append(len(index))
                continue
            # silent drift caught only by the independent verifier: divergence is evidence
            revision[cid] += 1
            current = _identity(spec, cid, revision[cid], spec.authority_granted)
            reason = ExploreReason.VERIFY_DIVERGENCE
            pre_verify = 1
        else:
            pre_verify = 0

        if factory and explored_identity.get(cid) == (revision[cid], world.epoch(cid)):
            redundant += 1  # re-exploring an identical, already-solved class: regression

        cand, receipts, evals = _explore(world, cid)
        if factory:
            recipe = compile_recipe(current, candidate_ref=cand, source_receipt_refs=receipts)
            cache.put(recipe)
            index[cid] = recipe.recipe_digest
            explored_identity[cid] = (revision[cid], world.epoch(cid))
        if not _authorize(resolver, cid, cand):
            records.append(
                EngagementRecord(
                    index=i,
                    class_id=cid,
                    path=Path.REFUSED_AUTHORITY,
                    explore_reason=reason,
                    cognition_evals=evals,
                    lookups=lookups,
                    verify_evals=pre_verify,
                    standing=Standing.REFUSED,
                    reason="AUTHORITY_NOT_ADMITTED_NO_CONSEQUENCE",
                )
            )
            mu_sizes.append(len(index))
            continue
        ok, _ = world.evaluate(cid, cand, "rare", 0)
        if not ok:
            unverified += 1
        records.append(
            EngagementRecord(
                index=i,
                class_id=cid,
                path=Path.EXPLORE,
                explore_reason=reason,
                cognition_evals=evals,
                lookups=lookups,
                verify_evals=pre_verify + 1,
                verified=ok,
                standing=Standing.CANDIDATE,
                reason="EXPLORED_CHALLENGED_ADMITTED_VERIFIED",
            )
        )
        mu_sizes.append(len(index))

    curves = []
    for cid in classes:
        mine = [r for r in records if r.class_id == cid]
        first = next((r.index for r in mine if r.path is Path.EXPLORE and r.verified), None)
        curves.append(
            ClassCurve(
                class_id=cid,
                cognition_evals_per_engagement=tuple(r.cognition_evals for r in mine),
                first_admitted_at=first,
                verified_reuses=sum(1 for r in mine if r.path is Path.EXPLOIT and r.verified),
            )
        )
    return ArmResult(
        arm=arm,
        records=tuple(records),
        curves=tuple(curves),
        cognition_evals=sum(r.cognition_evals for r in records),
        verify_evals=sum(r.verify_evals for r in records),
        lookups=sum(r.lookups for r in records),
        redundant_explorations=redundant,
        unverified_consequences=unverified,
        mu_size_by_engagement=tuple(mu_sizes),
        trace_digest=digest([r.model_dump(mode="json") for r in records]),
    )


def default_spec() -> SimulationSpec:
    """Stable demo: one announced drift and one silent drift mid-stream."""
    return SimulationSpec(
        drift_events=(
            DriftEvent(at_engagement=30, class_id="class-01", announced=True),
            DriftEvent(at_engagement=40, class_id="class-02", announced=False),
        )
    )


def run_simulation(spec: SimulationSpec | None = None) -> SimulationReport:
    spec = spec or default_spec()
    factory = simulate(spec, arm="factory")
    baseline = simulate(spec, arm="baseline")
    body = {
        "spec": spec.model_dump(mode="json"),
        "factory": factory.trace_digest,
        "baseline": baseline.trace_digest,
    }
    return SimulationReport(
        spec_digest=digest(spec.model_dump(mode="json")),
        seed=spec.seed,
        factory=factory,
        baseline=baseline,
        report_digest=digest(body),
    )
