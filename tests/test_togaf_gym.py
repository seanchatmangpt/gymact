"""Real, Chicago-style tests proving the *generated* TOGAF provider
(`gymact.gyms.togaf.build_togaf_provider()`, compiled from
`ggen/togaf-gym-pack/ontology.ttl` by the generic
`gymact.gyms.ontology_gym` compiler) satisfies the real kernel contract
across all ten ADM phases -- not a hand-coded environment.

No mocks: a real GymAct kernel, the real compiled provider, real
`TieredAuthorityResolver`/`DenyAuthorityResolver` authority decisions, and
real assertions on returned/observed state.
"""

from __future__ import annotations

from gymact import GymAct, MaterializationIntent
from gymact.gyms.ontology_gym import (
    TieredAuthorityResolver,
    capability_iri,
    inspect_capability_iri,
)
from gymact.gyms.togaf import build_togaf_provider
from gymact.models import ActuationIntent, Standing

STANDARD_REF = "urn:gymact:authority:togaf-m1-test-standard"
GOVERNANCE_REF = "urn:gymact:authority:togaf-m1-test-governance"

REQUIREMENT_SUBJECTS: tuple[str, ...] = (
    "urn:gymact:togaf:req:continuity",
    "urn:gymact:togaf:req:cost",
    "urn:gymact:togaf:req:latency",
    "urn:gymact:togaf:req:residency",
)


async def _materialize_tiered() -> tuple[GymAct, str]:
    provider = build_togaf_provider()
    resolver = TieredAuthorityResolver(
        elevated_capabilities=provider.elevated_capability_iris(),
        standard_ref=STANDARD_REF,
        elevated_ref=GOVERNANCE_REF,
    )
    gym = GymAct(authority_resolver=resolver)
    gym.register_provider(provider)
    materialization = await gym.materialize(
        MaterializationIntent(provider="togaf", config={})
    )
    assert materialization.accepted is True, materialization.receipt.reason
    assert materialization.episode is not None
    return gym, materialization.episode.episode_id


async def _walk_all_ten_phases(gym: GymAct, episode_id: str) -> None:
    """Establish every phase's artifact(s) in real ADM order, standard ref
    for phases through Migration Planning, governance ref for Phase G, then
    Phase H (which reopens Requirements Management as a real side effect)."""
    provider = build_togaf_provider()
    tasks = provider.tasks()
    assert len(tasks) == 10, "expected exactly the ten real TOGAF ADM tasks"

    for task in tasks:
        elevated = task.family in provider.elevated_task_families
        ref = GOVERNANCE_REF if elevated else STANDARD_REF
        iri = capability_iri(provider_name="togaf", task=task)
        if len(task.subjects) == 1:
            result = await gym.act(
                ActuationIntent(episode_id=episode_id, capability=iri, authority_ref=ref)
            )
            assert result.accepted is True, f"{task.identifier}: {result.receipt.reason}"
        else:
            for subject in task.subjects:
                result = await gym.act(
                    ActuationIntent(
                        episode_id=episode_id,
                        capability=iri,
                        payload={"subject": subject},
                        authority_ref=ref,
                    )
                )
                assert result.accepted is True, f"{task.identifier}:{subject}: {result.receipt.reason}"


async def test_all_ten_phases_walk_and_phase_h_reopens_requirements() -> None:
    gym, episode_id = await _materialize_tiered()

    await _walk_all_ten_phases(gym, episode_id)

    # Phase H (task-family "change") clears every Requirements Management
    # (task-family "requirements") fact as a real, documented side effect --
    # so goal_reached is False here even though every task including Phase H
    # itself actuated successfully.
    observation = await gym.observe(episode_id)
    assert observation.state["goal_reached"] is False
    established_requirements = {
        fact for fact in observation.state["facts"] if fact in REQUIREMENT_SUBJECTS
    }
    assert established_requirements == set(), (
        "Phase H must have cleared all four requirement facts, real loop-back"
    )

    # Recover: resubmit the four requirement subjects the change request
    # reopened.
    provider = build_togaf_provider()
    requirements_task = provider.tasks()[1]
    assert requirements_task.family == "requirements"
    requirements_iri = capability_iri(provider_name="togaf", task=requirements_task)
    for subject in requirements_task.subjects:
        result = await gym.act(
            ActuationIntent(
                episode_id=episode_id,
                capability=requirements_iri,
                payload={"subject": subject},
                authority_ref=STANDARD_REF,
            )
        )
        assert result.accepted is True, result.receipt.reason

    recovered = await gym.observe(episode_id)
    assert recovered.state["goal_reached"] is True

    verification = await gym.verify(episode_id, {"goal_reached": True})
    assert verification.passed is True

    await gym.teardown(episode_id, authority_ref=GOVERNANCE_REF)


async def test_governance_authority_is_separate_from_standard_authority() -> None:
    """A caller holding only the standard ref cannot approve their own
    architecture (Phase G) or raise a change (Phase H) -- the real,
    mechanically-enforced separation TieredAuthorityResolver provides."""
    gym, episode_id = await _materialize_tiered()
    provider = build_togaf_provider()
    tasks = provider.tasks()

    # Walk Preliminary through Migration Planning (indices 0-7) with the
    # standard ref only.
    for task in tasks[:8]:
        iri = capability_iri(provider_name="togaf", task=task)
        if len(task.subjects) == 1:
            result = await gym.act(
                ActuationIntent(episode_id=episode_id, capability=iri, authority_ref=STANDARD_REF)
            )
            assert result.accepted is True, result.receipt.reason
        else:
            for subject in task.subjects:
                result = await gym.act(
                    ActuationIntent(
                        episode_id=episode_id,
                        capability=iri,
                        payload={"subject": subject},
                        authority_ref=STANDARD_REF,
                    )
                )
                assert result.accepted is True, result.receipt.reason

    governance_task = tasks[8]
    assert governance_task.family == "governance"
    governance_iri = capability_iri(provider_name="togaf", task=governance_task)
    governance_subject = governance_task.subjects[0]

    refused = await gym.act(
        ActuationIntent(
            episode_id=episode_id,
            capability=governance_iri,
            payload={"subject": governance_subject},
            authority_ref=STANDARD_REF,
        )
    )
    assert refused.accepted is False
    assert refused.standing is Standing.REFUSED

    admitted = await gym.act(
        ActuationIntent(
            episode_id=episode_id,
            capability=governance_iri,
            payload={"subject": governance_subject},
            authority_ref=GOVERNANCE_REF,
        )
    )
    assert admitted.accepted is True, admitted.receipt.reason

    await gym.teardown(episode_id, authority_ref=GOVERNANCE_REF)


async def test_submitting_a_requirement_before_preliminary_is_refused() -> None:
    gym, episode_id = await _materialize_tiered()
    provider = build_togaf_provider()
    requirements_task = provider.tasks()[1]
    requirements_iri = capability_iri(provider_name="togaf", task=requirements_task)

    result = await gym.act(
        ActuationIntent(
            episode_id=episode_id,
            capability=requirements_iri,
            payload={"subject": REQUIREMENT_SUBJECTS[0]},
            authority_ref=STANDARD_REF,
        )
    )

    assert result.accepted is False
    assert result.standing is Standing.BLOCKED

    observation = await gym.observe(episode_id)
    assert observation.state["facts"] == []

    await gym.teardown(episode_id, authority_ref=GOVERNANCE_REF)


async def test_do_capability_is_refused_without_admitted_authority() -> None:
    """A plain GymAct() defaults to DenyAuthorityResolver -- the DO
    capability must be refused, not silently authorized."""
    provider = build_togaf_provider()
    gym = GymAct()
    gym.register_provider(provider)
    materialization = await gym.materialize(
        MaterializationIntent(provider="togaf", config={})
    )
    assert materialization.accepted is True, materialization.receipt.reason
    episode_id = materialization.episode.episode_id

    preliminary_task = provider.tasks()[0]
    preliminary_iri = capability_iri(provider_name="togaf", task=preliminary_task)

    result = await gym.act(
        ActuationIntent(episode_id=episode_id, capability=preliminary_iri)
    )

    assert result.accepted is False
    assert result.standing is Standing.REFUSED

    await gym.teardown(episode_id)


async def test_inspect_capability_is_a_real_read_and_reflects_current_state() -> None:
    gym, episode_id = await _materialize_tiered()
    provider = build_togaf_provider()
    preliminary_task = provider.tasks()[0]
    preliminary_iri = capability_iri(provider_name="togaf", task=preliminary_task)
    inspect_iri = inspect_capability_iri("togaf")

    before = await gym.observe(episode_id)
    assert before.state["facts"] == []

    result = await gym.act(
        ActuationIntent(
            episode_id=episode_id, capability=preliminary_iri, authority_ref=STANDARD_REF
        )
    )
    assert result.accepted is True, result.receipt.reason

    # inspect is a READ capability -- actuating it must be refused as
    # READ_CAPABILITY_IS_NOT_ACTUATION, matching every other gym's kernel
    # contract, not a togaf-specific rule.
    read_attempt = await gym.act(
        ActuationIntent(episode_id=episode_id, capability=inspect_iri, authority_ref=STANDARD_REF)
    )
    assert read_attempt.accepted is False

    after = await gym.observe(episode_id)
    assert after.state["facts"] == [preliminary_task.subjects[0]]

    await gym.teardown(episode_id, authority_ref=GOVERNANCE_REF)
