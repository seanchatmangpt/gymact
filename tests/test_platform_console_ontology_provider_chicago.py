"""Chicago court for the current platform-console ontology provider contract.

The Phase 4 provider consumes three bare ``sosa:Procedure`` facts. These tests
exercise that exact shape through the real RDF loader, provider, authority
resolver, GymAct kernel, and in-process ontology-driven environment. No mocks,
external credentials, HTTP transports, or live platform-console/cloud systems
are involved.
"""

from __future__ import annotations

from pathlib import Path

import anyio
import pytest

from gymact.gyms.ontology_gym import OntologyTask, TieredAuthorityResolver, capability_iri
from gymact.gyms.platform_console_ontology_provider import (
    PLATFORM_CONSOLE_GYM_PACK_DIR,
    PlatformConsoleOntologyDrivenProvider,
    build_platform_console_ontology_provider,
)
from gymact.kernel import GymAct
from gymact.models import ActuationIntent, MaterializationIntent, Standing

STANDARD_REF = "urn:gymact:authority-decision:pc-current-standard"
ELEVATED_REF = "urn:gymact:authority-decision:pc-current-elevated"
PROVIDER_NAME = "platform-console-ontology"
PCC = "https://seanchatmangpt.github.io/chatman-ecosystem/ontology/platform-console-capabilities#"

EXPECTED = {
    "castle.verb.inventory-components": (
        f"{PCC}CastleVerbInventoryComponents",
        "family-read",
    ),
    "castle.verb.inventory-goals": (f"{PCC}CastleVerbInventoryGoals", "family-read"),
    "approval.freeze-override": (f"{PCC}ApprovalFreezeOverride", "family-approval"),
}

_FIXTURE_TTL = f"""
@prefix pcc: <{PCC}> .
@prefix sosa: <http://www.w3.org/ns/sosa/> .
@prefix dct: <http://purl.org/dc/terms/> .

pcc:CastleVerbInventoryComponents a sosa:Procedure ;
    dct:identifier "castle.verb.inventory-components" ;
    dct:type pcc:family-read .

pcc:CastleVerbInventoryGoals a sosa:Procedure ;
    dct:identifier "castle.verb.inventory-goals" ;
    dct:type pcc:family-read .

pcc:ApprovalFreezeOverride a sosa:Procedure ;
    dct:identifier "approval.freeze-override" ;
    dct:type pcc:family-approval .
"""


def _write_pack(tmp_path: Path) -> Path:
    pack_dir = tmp_path / "platform-console-gym-pack"
    pack_dir.mkdir()
    (pack_dir / "ontology.ttl").write_text(_FIXTURE_TTL, encoding="utf-8")
    return pack_dir


def _task_map(
    provider: PlatformConsoleOntologyDrivenProvider,
) -> dict[str, OntologyTask]:
    return {task.identifier: task for task in provider.tasks()}


def test_explicit_pack_admission_compiles_current_three_procedures(tmp_path: Path) -> None:
    provider = build_platform_console_ontology_provider(pack_dir=_write_pack(tmp_path))

    tasks = _task_map(provider)

    assert set(tasks) == set(EXPECTED)
    for identifier, (task_iri, family) in EXPECTED.items():
        task = tasks[identifier]
        assert task.task_iri == task_iri
        assert task.family == family
        assert task.subjects == (task_iri,)


def test_default_pack_preserves_canonical_public_semantic_identities() -> None:
    ontology = PLATFORM_CONSOLE_GYM_PACK_DIR / "ontology.ttl"
    if not ontology.is_file():
        pytest.skip(f"canonical platform-console ontology pack not materialized at {ontology}")

    provider = build_platform_console_ontology_provider()
    tasks = _task_map(provider)

    assert set(tasks) == set(EXPECTED)
    assert {
        identifier: (task.task_iri, task.family) for identifier, task in tasks.items()
    } == EXPECTED


def test_standard_authority_admits_reads_and_refuses_approval_without_effect(
    tmp_path: Path,
) -> None:
    provider = build_platform_console_ontology_provider(pack_dir=_write_pack(tmp_path))
    resolver = TieredAuthorityResolver(
        elevated_capabilities=provider.elevated_capability_iris(),
        standard_ref=STANDARD_REF,
        elevated_ref=ELEVATED_REF,
    )
    tasks = _task_map(provider)

    async def run() -> None:
        gym = GymAct(authority_resolver=resolver)
        gym.register_provider(provider)
        materialized = await gym.materialize(
            MaterializationIntent(
                provider=PROVIDER_NAME,
                config={"requires_authority": True},
            )
        )
        assert materialized.accepted is True, materialized.receipt.reason
        assert materialized.episode is not None
        episode_id = materialized.episode.episode_id

        read_identifiers = (
            "castle.verb.inventory-components",
            "castle.verb.inventory-goals",
        )
        for identifier in read_identifiers:
            task = tasks[identifier]
            result = await gym.act(
                ActuationIntent(
                    episode_id=episode_id,
                    capability=capability_iri(
                        provider_name=PROVIDER_NAME,
                        task=task,
                    ),
                    authority_ref=STANDARD_REF,
                )
            )
            assert result.accepted is True, result.receipt.reason

        elevated_task = tasks["approval.freeze-override"]
        refused = await gym.act(
            ActuationIntent(
                episode_id=episode_id,
                capability=capability_iri(
                    provider_name=PROVIDER_NAME,
                    task=elevated_task,
                ),
                authority_ref=STANDARD_REF,
            )
        )
        assert refused.accepted is False
        assert refused.standing is Standing.REFUSED
        assert refused.effect is None

        observed = await gym.observe(episode_id)
        assert elevated_task.task_iri not in observed.state["facts"]
        expected_read_facts = {tasks[name].task_iri for name in read_identifiers}
        assert expected_read_facts <= set(observed.state["facts"])
        await gym.teardown(episode_id, authority_ref=ELEVATED_REF)

    anyio.run(run)


def test_elevated_authority_admits_approval_through_real_kernel(tmp_path: Path) -> None:
    provider = build_platform_console_ontology_provider(pack_dir=_write_pack(tmp_path))
    resolver = TieredAuthorityResolver(
        elevated_capabilities=provider.elevated_capability_iris(),
        standard_ref=STANDARD_REF,
        elevated_ref=ELEVATED_REF,
    )
    approval = _task_map(provider)["approval.freeze-override"]

    async def run() -> None:
        gym = GymAct(authority_resolver=resolver)
        gym.register_provider(provider)
        materialized = await gym.materialize(
            MaterializationIntent(
                provider=PROVIDER_NAME,
                config={"requires_authority": True},
            )
        )
        assert materialized.accepted is True, materialized.receipt.reason
        assert materialized.episode is not None
        episode_id = materialized.episode.episode_id

        result = await gym.act(
            ActuationIntent(
                episode_id=episode_id,
                capability=capability_iri(
                    provider_name=PROVIDER_NAME,
                    task=approval,
                ),
                authority_ref=ELEVATED_REF,
            )
        )
        assert result.accepted is True, result.receipt.reason
        assert result.effect is not None
        assert result.effect["established"] == approval.task_iri

        observed = await gym.observe(episode_id)
        assert approval.task_iri in observed.state["facts"]
        await gym.teardown(episode_id, authority_ref=ELEVATED_REF)

    anyio.run(run)


def test_missing_admitted_pack_refuses_materialization_instead_of_inventing_tasks(
    tmp_path: Path,
) -> None:
    missing = tmp_path / "not-materialized"
    provider = build_platform_console_ontology_provider(pack_dir=missing)

    async def run() -> None:
        await provider.materialize(
            scenario=None,
            config={"requires_authority": True},
        )

    with pytest.raises(ValueError, match="NO_TASKS_FOUND_IN_PACK"):
        anyio.run(run)
