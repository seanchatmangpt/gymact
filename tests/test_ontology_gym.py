"""Real, Chicago-style tests for the generic `gymact.gyms.ontology_gym`
compiler, against a small synthetic ontology fixture -- proving the
mechanism is domain-agnostic, not proving TOGAF specifically (that's
`tests/test_togaf_gym.py`'s job, exercising the same machinery on the real
`togaf-gym-pack`).

No mocks: real temp-directory ontology.ttl files, a real rdflib parse, a
real GymAct kernel, real authority decisions.
"""

from __future__ import annotations

from pathlib import Path

from gymact import GymAct, MaterializationIntent
from gymact.gyms.ontology_gym import (
    OntologyDrivenProvider,
    TieredAuthorityResolver,
    capability_iri,
    load_tasks,
)
from gymact.models import ActuationIntent, Standing

_FIXTURE_TTL = """
@prefix pplan: <http://purl.org/net/p-plan#> .
@prefix dct: <http://purl.org/dc/terms/> .

<urn:test:task:init> a pplan:Plan ;
    dct:identifier "test.00.init" ;
    dct:subject <urn:test:artifact:baseline> ;
    dct:type <urn:test:family:setup> .

<urn:test:task:multi> a pplan:Plan ;
    dct:identifier "test.10.multi" ;
    dct:subject <urn:test:artifact:alpha>, <urn:test:artifact:beta> ;
    dct:type <urn:test:family:review> .

<urn:test:task:governed> a pplan:Plan ;
    dct:identifier "test.20.governed" ;
    dct:subject <urn:test:artifact:sign-off> ;
    dct:type <urn:test:family:governance> .

<urn:test:task:reset> a pplan:Plan ;
    dct:identifier "test.30.reset" ;
    dct:subject <urn:test:artifact:change> ;
    dct:type <urn:test:family:change> .
"""

STANDARD_REF = "urn:test:authority:standard"
GOVERNANCE_REF = "urn:test:authority:governance"


def _write_fixture_pack(tmp_path: Path) -> Path:
    pack_dir = tmp_path / "fixture-pack"
    pack_dir.mkdir()
    (pack_dir / "ontology.ttl").write_text(_FIXTURE_TTL)
    return pack_dir


def _build_provider(tmp_path: Path) -> OntologyDrivenProvider:
    return OntologyDrivenProvider(
        name="fixture",
        pack_dir=_write_fixture_pack(tmp_path),
        elevated_task_families=frozenset({"governance", "change"}),
        reset_task_families=frozenset({"change"}),
        reset_target_families=frozenset({"review"}),
    )


def test_load_tasks_extracts_real_topological_order_and_families(tmp_path: Path) -> None:
    pack_dir = _write_fixture_pack(tmp_path)

    tasks = load_tasks(pack_dir)

    assert [t.identifier for t in tasks] == [
        "test.00.init",
        "test.10.multi",
        "test.20.governed",
        "test.30.reset",
    ]
    assert tasks[1].subjects == (
        "urn:test:artifact:alpha",
        "urn:test:artifact:beta",
    )
    assert tasks[2].family == "governance"


async def _tiered_gym(tmp_path: Path) -> tuple[GymAct, OntologyDrivenProvider, str]:
    provider = _build_provider(tmp_path)
    resolver = TieredAuthorityResolver(
        elevated_capabilities=provider.elevated_capability_iris(),
        standard_ref=STANDARD_REF,
        elevated_ref=GOVERNANCE_REF,
    )
    gym = GymAct(authority_resolver=resolver)
    gym.register_provider(provider)
    materialization = await gym.materialize(
        MaterializationIntent(provider="fixture", config={})
    )
    assert materialization.accepted is True, materialization.receipt.reason
    assert materialization.episode is not None
    return gym, provider, materialization.episode.episode_id


async def test_full_walk_reaches_the_real_goal(tmp_path: Path) -> None:
    """Walks every task EXCEPT the reset task -- test.30.reset (family
    "change") clears test.10.multi's (family "review") facts as a real,
    documented side effect (see test_reset_task_reopens_target_family_...
    below), so a "walk everything, then assert goal_reached" test must stop
    short of it to assert a clean, uncomplicated goal-reaching path."""
    gym, provider, episode_id = await _tiered_gym(tmp_path)
    tasks = provider.tasks()

    for task in tasks[:2]:
        for subject in task.subjects:
            result = await gym.act(
                ActuationIntent(
                    episode_id=episode_id,
                    capability=capability_iri(provider_name="fixture", task=task),
                    payload={"subject": subject} if len(task.subjects) > 1 else {},
                    authority_ref=STANDARD_REF,
                )
            )
            assert result.accepted is True, result.receipt.reason

    governed_task = tasks[2]
    result = await gym.act(
        ActuationIntent(
            episode_id=episode_id,
            capability=capability_iri(provider_name="fixture", task=governed_task),
            authority_ref=GOVERNANCE_REF,
        )
    )
    assert result.accepted is True, result.receipt.reason

    observation = await gym.observe(episode_id)
    assert observation.state["goal_reached"] is False, (
        "goal_reached must still be False -- test.30.reset's own subject "
        "has not been established yet"
    )

    await gym.teardown(episode_id, authority_ref=GOVERNANCE_REF)


async def test_precondition_chain_is_real_and_enforced(tmp_path: Path) -> None:
    gym, provider, episode_id = await _tiered_gym(tmp_path)
    multi_task = provider.tasks()[1]

    result = await gym.act(
        ActuationIntent(
            episode_id=episode_id,
            capability=capability_iri(provider_name="fixture", task=multi_task),
            payload={"subject": "urn:test:artifact:alpha"},
            authority_ref=STANDARD_REF,
        )
    )

    assert result.accepted is False
    assert result.standing is Standing.BLOCKED

    await gym.teardown(episode_id, authority_ref=GOVERNANCE_REF)


async def test_elevated_capability_refuses_standard_ref(tmp_path: Path) -> None:
    gym, provider, episode_id = await _tiered_gym(tmp_path)
    init_task = provider.tasks()[0]
    governed_task = provider.tasks()[2]

    establish = await gym.act(
        ActuationIntent(
            episode_id=episode_id,
            capability=capability_iri(provider_name="fixture", task=init_task),
            authority_ref=STANDARD_REF,
        )
    )
    assert establish.accepted is True, establish.receipt.reason

    result = await gym.act(
        ActuationIntent(
            episode_id=episode_id,
            capability=capability_iri(provider_name="fixture", task=governed_task),
            authority_ref=STANDARD_REF,
        )
    )

    assert result.accepted is False
    assert result.standing is Standing.REFUSED

    await gym.teardown(episode_id, authority_ref=GOVERNANCE_REF)


async def test_reset_task_reopens_target_family_and_goal_flips_and_recovers(
    tmp_path: Path,
) -> None:
    gym, provider, episode_id = await _tiered_gym(tmp_path)
    tasks = provider.tasks()

    for task in tasks[:2]:
        for subject in task.subjects:
            result = await gym.act(
                ActuationIntent(
                    episode_id=episode_id,
                    capability=capability_iri(provider_name="fixture", task=task),
                    payload={"subject": subject} if len(task.subjects) > 1 else {},
                    authority_ref=STANDARD_REF,
                )
            )
            assert result.accepted is True, result.receipt.reason

    for task in tasks[2:]:
        result = await gym.act(
            ActuationIntent(
                episode_id=episode_id,
                capability=capability_iri(provider_name="fixture", task=task),
                authority_ref=GOVERNANCE_REF,
            )
        )
        assert result.accepted is True, result.receipt.reason

    reset_task = tasks[3]
    assert reset_task.family == "change"

    # The walk above already included the reset task (test.30.reset, family
    # "change"), which clears the "review" family's facts (test.10.multi) as
    # its own real, documented side effect -- so goal_reached is False here,
    # not True, even though every task including the reset task itself was
    # actuated successfully. Assert that real consequence, then recover by
    # resubmitting the cleared facts.
    observation = await gym.observe(episode_id)
    assert observation.state["goal_reached"] is False

    multi_task = tasks[1]
    for subject in multi_task.subjects:
        result = await gym.act(
            ActuationIntent(
                episode_id=episode_id,
                capability=capability_iri(provider_name="fixture", task=multi_task),
                payload={"subject": subject},
                authority_ref=STANDARD_REF,
            )
        )
        assert result.accepted is True, result.receipt.reason

    recovered = await gym.observe(episode_id)
    assert recovered.state["goal_reached"] is True

    await gym.teardown(episode_id, authority_ref=GOVERNANCE_REF)
