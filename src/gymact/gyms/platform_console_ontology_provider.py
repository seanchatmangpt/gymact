"""`gymact.gyms.ontology_gym.OntologyDrivenProvider`, pointed at the real
`platform-console-capability-pack`'s `ontology.ttl`
(`/Users/sac/ggen-marketplace/packs/platform-console-capability-pack/
ontology.ttl`) -- the ~30 ground-truth platform-console capabilities
enumerated across `castle.ts` (CASTLE inventory verbs), `approval-
workflow.ts` (`ACTIONS_REQUIRING_APPROVAL` maker-checker set), and the
capability-intrinsic-not-yet-authority-gated set in `k8s.ts`/`orgs.ts`/
`capacity-reservations.ts`/`partners.ts`.

Real shape confirmed by direct read of that file before writing this module
(NOT `togaf-gym-pack`'s `pplan:Plan` shape, NOT `protocol-gym-pack`'s bare
`dct:identifier`-bearing `sosa:Procedure` shape `ontology_gym.load_procedures`
already handles): every individual is `a ce:Capability, sosa:Procedure`,
carrying `dct:title` (a stable slug like `"org.delete"`, not `dct:identifier`
-- so neither `load_tasks` nor `load_procedures` fits verbatim), `dct:type`
pointing at `urn:gymact:consequence:{read,do}`, and, load-bearing for this
module, a real `ce:reversible` boolean literal per capability. This module
therefore ships its own small SPARQL loader (`_load_capabilities`) rather
than reusing `load_tasks`/`load_procedures` wholesale, then reuses
`OntologyDrivenEnvironment`/`OntologyDrivenProvider` unmodified via the same
`OntologyTask` shape those two already produce -- the same "mechanically
compiled, no per-domain Python" contract `togaf.py` demonstrates, adapted to
a genuinely different real ontology shape.

Fail-closed authority binding for the IRREVERSIBLE/destructive/financial set
(`org.delete`, `dr.failover`, `dsar.erasure`, `sla.credit.apply`,
`patch-sla.credit.apply`, `k8s.createRestoreJob`, `k8s.deleteProject`,
`orgs.deleteOrg` -- exactly the eight capabilities this pack's own
`ce:reversible false` triples name, read from the ontology, never
hand-enumerated separately and therefore never able to drift from the real
data): `family = "irreversible"` for every one of them (derived from
`ce:reversible`, not guessed from the title string), fed to
`OntologyDrivenProvider(elevated_task_families={"irreversible"})` so
`elevated_capability_iris()` names exactly this set, then bound to a
`TieredAuthorityResolver` via `build_fail_closed_authority_resolver()` whose
`elevated_ref` is a caller-supplied, separately-configured allow-list value
-- never the same ref as `standard_ref`, and never admitted by omission:
`TieredAuthorityResolver.authorize` (`ontology_gym.py:527-541`) already
denies any `elevated`-family capability whose `authority_ref` is not
literally `elevated_ref`, so a caller who never configures a real elevated
allow-list gets a resolver that DENIES every irreversible capability
unconditionally (there is no default elevated_ref that admits anything --
`build_fail_closed_authority_resolver` requires the caller to name one
explicitly, and passing the same value for both refs is rejected outright).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from rdflib import Graph

from gymact.gyms.ontology_gym import (
    OntologyDrivenProvider,
    OntologyTask,
    TieredAuthorityResolver,
    _load_pack_graph,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_PACK_DIR = (
    Path.home() / "ggen-marketplace" / "packs" / "platform-console-capability-pack"
)

PROVIDER_NAME = "platform-console-ontology"

# The real, checkable derivation this module makes: "irreversible" iff this
# pack's own `ce:reversible` triple says `false`. Nothing else. See module
# docstring for the exact eight-capability set this currently names.
IRREVERSIBLE_FAMILY = "irreversible"
REVERSIBLE_FAMILY = "reversible"
ELEVATED_TASK_FAMILIES = frozenset({IRREVERSIBLE_FAMILY})

_CAPABILITY_QUERY = """
PREFIX ce: <https://seanchatmangpt.github.io/chatman-ecosystem/ontology/capabilities#>
PREFIX sosa: <http://www.w3.org/ns/sosa/>
PREFIX dct: <http://purl.org/dc/terms/>
SELECT ?capability ?title ?reversible WHERE {
  ?capability a ce:Capability, sosa:Procedure ;
              dct:title ?title ;
              ce:reversible ?reversible .
}
"""


@dataclass(frozen=True)
class PlatformConsoleCapabilityFact:
    """One real capability fact read from the pack's ontology, before being
    folded into an `OntologyTask` -- kept as its own type so
    `load_platform_console_capabilities` is independently testable against
    the real graph without going through `OntologyTask`'s TOGAF-shaped
    field names."""

    capability_iri: str
    title: str
    reversible: bool


def load_platform_console_capabilities(
    pack_dir: Path = DEFAULT_PACK_DIR,
) -> tuple[PlatformConsoleCapabilityFact, ...]:
    """Real SPARQL read of every `ce:Capability`/`sosa:Procedure` individual
    in the pack, with its real `dct:title` and `ce:reversible` literal --
    the two fields this module's fail-closed binding depends on. No
    `dct:identifier` exists in this pack's real ontology (confirmed by
    direct grep before writing this function), so this bypasses
    `ontology_gym.load_tasks`/`load_procedures` (both require it) and reads
    the graph directly via `_load_pack_graph`, the same loader those two
    functions use internally."""
    graph: Graph = _load_pack_graph(pack_dir)
    facts: list[PlatformConsoleCapabilityFact] = []
    for capability, title, reversible in graph.query(_CAPABILITY_QUERY):
        facts.append(
            PlatformConsoleCapabilityFact(
                capability_iri=str(capability),
                title=str(title),
                reversible=bool(reversible.toPython()),
            )
        )
    return tuple(sorted(facts, key=lambda f: f.title))


def _as_ontology_tasks(
    facts: tuple[PlatformConsoleCapabilityFact, ...],
) -> tuple[OntologyTask, ...]:
    """Fold the pack's real capability facts into the `OntologyTask` shape
    `OntologyDrivenEnvironment`/`OntologyDrivenProvider` already know how to
    serve -- `identifier` is the real `dct:title` slug (used verbatim as
    this environment's real fact/subject, since these capabilities have no
    TOGAF-style multi-subject artifact model), `family` is derived solely
    from the real `ce:reversible` triple, never from the title string."""
    return tuple(
        OntologyTask(
            task_iri=fact.capability_iri,
            identifier=fact.title,
            subjects=(fact.title,),
            family=IRREVERSIBLE_FAMILY if not fact.reversible else REVERSIBLE_FAMILY,
        )
        for fact in facts
    )


class PlatformConsoleOntologyProvider(OntologyDrivenProvider):
    """`OntologyDrivenProvider` bound to the real platform-console capability
    pack. Overrides `tasks()` to use this module's own SPARQL loader
    (`load_platform_console_capabilities`) instead of the base class's
    `load_tasks` (which requires `dct:identifier`, absent from this pack's
    real ontology) -- everything else (precondition chain, actuate/verify/
    checkpoint, `elevated_capability_iris()`) is the unmodified base-class
    machinery `togaf.py` already exercises."""

    def __init__(self, *, pack_dir: Path = DEFAULT_PACK_DIR) -> None:
        super().__init__(
            name=PROVIDER_NAME,
            pack_dir=pack_dir,
            elevated_task_families=ELEVATED_TASK_FAMILIES,
        )

    def tasks(self) -> tuple[OntologyTask, ...]:
        return _as_ontology_tasks(load_platform_console_capabilities(self._pack_dir))


def build_platform_console_ontology_provider(
    pack_dir: Path = DEFAULT_PACK_DIR,
) -> PlatformConsoleOntologyProvider:
    return PlatformConsoleOntologyProvider(pack_dir=pack_dir)


def build_fail_closed_authority_resolver(
    *,
    provider: PlatformConsoleOntologyProvider,
    standard_ref: str,
    elevated_ref: str | None,
) -> TieredAuthorityResolver:
    """Build the real `TieredAuthorityResolver` binding every IRREVERSIBLE
    capability this provider's ontology names to fail-closed-by-default
    authority.

    `elevated_ref` is the separately-configured allow-list value a caller
    must explicitly name to grant IRREVERSIBLE actuation (e.g. read from a
    deploy-time secret naming a real change-management/on-call approver
    identity) -- never invented here, never defaulted to something that
    admits by omission. Passing `elevated_ref=None` (no elevated allow-list
    configured at all) is the explicit fail-closed case: this resolver is
    still constructed and still real, but its `elevated_ref` is set to a
    sentinel IRI (`urn:gymact:authority-decision:no-elevated-allowlist-
    configured`) that `TieredAuthorityResolver.authorize` can never match
    against any real caller-supplied `authority_ref`, since no real
    `AuthorityRequest` will ever legitimately carry that literal string --
    every IRREVERSIBLE request is therefore denied
    (`reason="AUTHORITY_NOT_ADMITTED"`), and passing `elevated_ref` equal to
    `standard_ref` is rejected outright rather than silently admitting
    IRREVERSIBLE capabilities to standard-tier callers."""
    if elevated_ref is not None and elevated_ref == standard_ref:
        raise ValueError(
            "REFUSED_SAME_REF_FOR_STANDARD_AND_ELEVATED: fail-closed binding "
            "requires elevated_ref to differ from standard_ref, otherwise "
            "every standard-tier caller would be admitted for IRREVERSIBLE "
            "capabilities."
        )
    resolved_elevated_ref = (
        elevated_ref
        if elevated_ref is not None
        else "urn:gymact:authority-decision:no-elevated-allowlist-configured"
    )
    return TieredAuthorityResolver(
        elevated_capabilities=provider.elevated_capability_iris(),
        standard_ref=standard_ref,
        elevated_ref=resolved_elevated_ref,
    )


# Backward-compatible builder alias, matching `togaf.py`'s `TogafProvider`
# naming convention.
PlatformConsoleOntologyProviderFactory = build_platform_console_ontology_provider
