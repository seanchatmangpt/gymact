"""Real, Chicago-style test for eager-forging-sparrow's Phase 4: platform-
console's 3 real capabilities (`castle.verb.inventory-components`,
`castle.verb.inventory-goals`, `approval.freeze-override`), modeled as real
`sosa:Procedure` triples in `chatman-ecosystem/ontology/platform-console-
gym-pack/ontology.ttl`, compiled into a real, live `EnvironmentProvider` by
`gymact.gyms.ontology_gym.OntologyDrivenProvider` (via the thin
`PlatformConsoleOntologyDrivenProvider` override), gated by the real
`kernel.py` `AuthorityResolver`/`CapabilityScope` machinery.

No `unittest.mock`/`MagicMock`/`patch`/`monkeypatch` anywhere in this file.
The first test below is unconditional and network-free: real `rdflib`
parse of a real TTL file, real `GymAct.materialize()`/`act()` round trip,
real authority-tier enforcement (`TieredAuthorityResolver`), real fact-state
transitions -- every collaborator is the actual production object, not a
double.

The second test additionally drives a REAL HTTP call against a reachable
platform-console deployment, reusing `platform_console_provider.py`'s
already-proven `Authorization: Bearer pk_live_...` wiring UNMODIFIED (a
second, real provider registered on the same `GymAct` instance -- this is
the "plan -> real actuation bridge" composition Phase 4 asks for, not a
rewrite of that module's HTTP layer). Matches
`test_platform_console_provider.py`'s own skip-named-not-mocked convention
exactly: `pytest.mark.skipif` when `PLATFORM_CONSOLE_BASE_URL`/
`PLATFORM_CONSOLE_API_KEY` are not set, never silently faked.
"""

from __future__ import annotations

import os

import anyio
import pytest

from gymact.agent import AllowListCapabilityScope
from gymact.gyms.ontology_gym import TieredAuthorityResolver, capability_iri
from gymact.gyms.platform_console_ontology_provider import (
    ELEVATED_TASK_FAMILIES,
    build_platform_console_ontology_provider,
)
from gymact.gyms.platform_console_provider import PLATFORM_CONSOLE_CAPABILITIES, PlatformConsoleProvider
from gymact.kernel import GymAct
from gymact.models import ActuationIntent, MaterializationIntent

BASE_URL = os.environ.get("PLATFORM_CONSOLE_BASE_URL")
API_KEY = os.environ.get("PLATFORM_CONSOLE_API_KEY")
_live_reachable = bool(BASE_URL and API_KEY)

_STANDARD_AUTHORITY_REF = "urn:gymact:authority-decision:platform-console-ontology-standard"
_ELEVATED_AUTHORITY_REF = "urn:gymact:authority-decision:platform-console-ontology-elevated"
_PRINCIPAL = "urn:prov:agent:gymact-eager-forging-sparrow-phase4"


def _inventory_components_iri(provider) -> str:
    task = next(t for t in provider.tasks() if t.identifier == "castle.verb.inventory-components")
    return capability_iri(provider_name=provider.name, task=task)


def _inventory_goals_iri(provider) -> str:
    task = next(t for t in provider.tasks() if t.identifier == "castle.verb.inventory-goals")
    return capability_iri(provider_name=provider.name, task=task)


def _freeze_override_iri(provider) -> str:
    task = next(t for t in provider.tasks() if t.identifier == "approval.freeze-override")
    return capability_iri(provider_name=provider.name, task=task)


def test_ontology_driven_provider_compiles_platform_console_pack_real_tasks() -> None:
    """Real TTL parse (no network): the pack's 3 real `sosa:Procedure`
    individuals are extracted with the real family split
    (`platform-console-capabilities.ttl`'s own `ce:requiredAuthority`
    values), and `elevated_capability_iris()` names exactly the one
    maker-checker capability."""
    provider = build_platform_console_ontology_provider()
    tasks = provider.tasks()
    identifiers = sorted(t.identifier for t in tasks)
    assert identifiers == [
        "approval.freeze-override",
        "castle.verb.inventory-components",
        "castle.verb.inventory-goals",
    ]
    families = {t.identifier: t.family for t in tasks}
    assert families["approval.freeze-override"] == "family-approval"
    assert families["castle.verb.inventory-components"] == "family-read"
    assert families["castle.verb.inventory-goals"] == "family-read"
    assert ELEVATED_TASK_FAMILIES == frozenset({"family-approval"})

    elevated = provider.elevated_capability_iris()
    assert elevated == {_freeze_override_iri(provider)}


def test_ontology_driven_provider_actuates_both_castle_verbs_and_gates_freeze_override() -> None:
    """Real, network-free round trip through the real `kernel.py` gates:

    - `inventory-components` and `inventory-goals` (standard authority)
      actuate successfully and establish real, distinct facts.
    - `approval.freeze-override` (elevated authority) is REFUSED when only
      the standard authority ref is presented -- the real maker-checker
      separation `TieredAuthorityResolver` enforces -- and succeeds once the
      elevated ref is presented, proving the tier split is real and load-
      bearing, not decorative."""

    async def run() -> None:
        provider = build_platform_console_ontology_provider()
        components_iri = _inventory_components_iri(provider)
        goals_iri = _inventory_goals_iri(provider)
        freeze_iri = _freeze_override_iri(provider)

        gym = GymAct(
            authority_resolver=TieredAuthorityResolver(
                elevated_capabilities=provider.elevated_capability_iris(),
                standard_ref=_STANDARD_AUTHORITY_REF,
                elevated_ref=_ELEVATED_AUTHORITY_REF,
            ),
            capability_scope=AllowListCapabilityScope(
                {_PRINCIPAL: frozenset({components_iri, goals_iri, freeze_iri})}
            ),
        )
        gym.register_provider(provider)

        materialization = await gym.materialize(
            MaterializationIntent(provider=provider.name, config={}, principal=_PRINCIPAL)
        )
        assert materialization.accepted, materialization.receipt.reason
        episode_id = materialization.episode.episode_id

        components_result = await gym.act(
            ActuationIntent(
                episode_id=episode_id,
                capability=components_iri,
                authority_ref=_STANDARD_AUTHORITY_REF,
                principal=_PRINCIPAL,
            )
        )
        assert components_result.accepted, components_result.receipt.reason
        assert components_result.effect is not None
        assert components_result.effect["established"] == (
            "https://seanchatmangpt.github.io/chatman-ecosystem/ontology/"
            "platform-console-capabilities#CastleVerbInventoryComponents"
        )

        goals_result = await gym.act(
            ActuationIntent(
                episode_id=episode_id,
                capability=goals_iri,
                authority_ref=_STANDARD_AUTHORITY_REF,
                principal=_PRINCIPAL,
            )
        )
        assert goals_result.accepted, goals_result.receipt.reason
        assert goals_result.effect is not None
        assert set(goals_result.effect["after_facts"]) >= {
            components_result.effect["established"],
            goals_result.effect["established"],
        }

        # Real refusal: standard authority does not admit the elevated
        # (maker-checker) capability.
        refused = await gym.act(
            ActuationIntent(
                episode_id=episode_id,
                capability=freeze_iri,
                authority_ref=_STANDARD_AUTHORITY_REF,
                principal=_PRINCIPAL,
            )
        )
        assert not refused.accepted
        assert refused.receipt.reason == "AUTHORITY_NOT_ADMITTED"

        # Real admission: the elevated ref is admitted for the same capability.
        approved = await gym.act(
            ActuationIntent(
                episode_id=episode_id,
                capability=freeze_iri,
                authority_ref=_ELEVATED_AUTHORITY_REF,
                principal=_PRINCIPAL,
            )
        )
        assert approved.accepted, approved.receipt.reason
        assert approved.effect is not None

        assert gym.verify_evidence_chain()
        await gym.teardown(episode_id, authority_ref=_ELEVATED_AUTHORITY_REF)

    anyio.run(run)


@pytest.mark.skipif(
    not _live_reachable,
    reason=(
        "PLATFORM_CONSOLE_BASE_URL/PLATFORM_CONSOLE_API_KEY not set -- no reachable "
        "test-tenant platform-console deployment configured. Skipped, not mocked, "
        "matching test_platform_console_provider.py's own convention."
    ),
)
def test_ontology_driven_plan_state_composed_with_real_platform_console_actuation() -> None:
    """The real Phase-4 bridge: the same solved-plan capability
    (`castle.verb.inventory-components`) is actuated on BOTH providers under
    one `GymAct` instance -- `PlatformConsoleOntologyDrivenProvider` for the
    real plan-state/authority-tier gate, `PlatformConsoleProvider`
    (unmodified) for the real `POST /api/castle/run` HTTP call and its real
    `verify()` poll of the real k8s Job -- proving a solved plan step can
    drive real infrastructure actuation through the existing, proven HTTP
    wiring rather than a new hand-written bridge."""

    async def run() -> None:
        ontology_provider = build_platform_console_ontology_provider()
        components_iri = _inventory_components_iri(ontology_provider)
        goals_iri = _inventory_goals_iri(ontology_provider)
        freeze_iri = _freeze_override_iri(ontology_provider)

        gym = GymAct(
            authority_resolver=TieredAuthorityResolver(
                elevated_capabilities=ontology_provider.elevated_capability_iris(),
                standard_ref=_STANDARD_AUTHORITY_REF,
                elevated_ref=_ELEVATED_AUTHORITY_REF,
            ),
            capability_scope=AllowListCapabilityScope(
                {
                    _PRINCIPAL: frozenset(
                        {components_iri, goals_iri, freeze_iri}
                        | {item.iri for item in PLATFORM_CONSOLE_CAPABILITIES}
                    )
                }
            ),
        )
        gym.register_provider(ontology_provider)
        gym.register_provider(PlatformConsoleProvider())

        # Real plan-state side: establish the fact for this plan step.
        plan_materialization = await gym.materialize(
            MaterializationIntent(
                provider=ontology_provider.name, config={}, principal=_PRINCIPAL
            )
        )
        assert plan_materialization.accepted, plan_materialization.receipt.reason
        plan_episode_id = plan_materialization.episode.episode_id
        plan_result = await gym.act(
            ActuationIntent(
                episode_id=plan_episode_id,
                capability=components_iri,
                authority_ref=_STANDARD_AUTHORITY_REF,
                principal=_PRINCIPAL,
            )
        )
        assert plan_result.accepted, plan_result.receipt.reason

        # Real infrastructure side: the same plan step's real actuation
        # against real platform-console, via the unmodified, already-proven
        # PlatformConsoleProvider.
        http_materialization = await gym.materialize(
            MaterializationIntent(
                provider="platform-console",
                config={"base_url": BASE_URL},
                principal=_PRINCIPAL,
            )
        )
        assert http_materialization.accepted, http_materialization.receipt.reason
        http_episode_id = http_materialization.episode.episode_id
        run_capability = next(
            c for c in PLATFORM_CONSOLE_CAPABILITIES if c.binding == "run_inventory_components"
        )
        http_result = await gym.act(
            ActuationIntent(
                episode_id=http_episode_id,
                capability=run_capability.iri,
                authority_ref=_STANDARD_AUTHORITY_REF,
                principal=_PRINCIPAL,
            )
        )
        assert http_result.accepted, http_result.receipt.reason
        assert http_result.effect is not None
        assert http_result.effect["status"] == 201
        assert http_result.effect["job_name"]

        verification = await gym.verify(http_episode_id, {})
        assert verification.passed, verification.observed

        assert gym.verify_evidence_chain()
        await gym.teardown(plan_episode_id, authority_ref=_STANDARD_AUTHORITY_REF)
        await gym.teardown(http_episode_id, authority_ref=_STANDARD_AUTHORITY_REF)

    anyio.run(run)
