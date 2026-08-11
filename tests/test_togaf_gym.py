"""Real, Chicago-style tests for the TOGAF Preliminary/Requirements gym (M1).

No mocks: a real `GymAct` kernel, a real `TogafEnvironment`, real
`AllowListAuthorityResolver`/`DenyAuthorityResolver` authority decisions, and
real assertions on returned state -- not on "was a method called."
"""

from __future__ import annotations

from gymact import AllowListAuthorityResolver, GymAct, MaterializationIntent
from gymact.gyms.togaf import (
    CAPABILITY_ESTABLISH,
    CAPABILITY_SUBMIT,
    REQUIREMENT_SUBJECTS,
    TogafProvider,
)
from gymact.models import ActuationIntent, Standing

AUTHORITY = "urn:gymact:authority:togaf-m1-test"


async def _materialize_authorized() -> tuple[GymAct, str]:
    gym = GymAct(authority_resolver=AllowListAuthorityResolver({AUTHORITY}))
    gym.register_provider(TogafProvider())
    materialization = await gym.materialize(
        MaterializationIntent(provider="togaf", config={})
    )
    assert materialization.accepted is True, materialization.receipt.reason
    assert materialization.episode is not None
    return gym, materialization.episode.episode_id


async def _establish(gym: GymAct, episode_id: str):
    return await gym.act(
        ActuationIntent(
            episode_id=episode_id,
            capability=CAPABILITY_ESTABLISH,
            authority_ref=AUTHORITY,
        )
    )


async def _submit(gym: GymAct, episode_id: str, requirement: str):
    return await gym.act(
        ActuationIntent(
            episode_id=episode_id,
            capability=CAPABILITY_SUBMIT,
            payload={"requirement": requirement},
            authority_ref=AUTHORITY,
        )
    )


async def test_establish_then_submit_all_requirements_reaches_the_real_goal() -> None:
    gym, episode_id = await _materialize_authorized()

    establish_result = await _establish(gym, episode_id)
    assert establish_result.accepted is True, establish_result.receipt.reason
    assert establish_result.standing is Standing.ALIVE

    for requirement in REQUIREMENT_SUBJECTS:
        submit_result = await _submit(gym, episode_id, requirement)
        assert submit_result.accepted is True, submit_result.receipt.reason

    observation = await gym.observe(episode_id)
    assert observation.state["goal_reached"] is True
    assert set(observation.state["facts"]) == {
        "capability:architecture-established",
        *(f"requirement:{r}:submitted" for r in REQUIREMENT_SUBJECTS),
    }

    verification = await gym.verify(episode_id, {"goal_reached": True})
    assert verification.passed is True

    await gym.teardown(episode_id, authority_ref=AUTHORITY)


async def test_submitting_a_requirement_before_establishment_is_refused() -> None:
    """The kernel wraps a provider's raw exception as PROVIDER_ERROR:<type> and
    does not surface the message (same behavior every other gym's raw-ValueError
    refusals get -- see kernel.py's act() exception handler), so the real,
    meaningful assertion here is on state: the refused submission must leave
    no requirement fact recorded, not on the (kernel-owned, opaque) reason
    string."""
    gym, episode_id = await _materialize_authorized()

    result = await _submit(gym, episode_id, "continuity")

    assert result.accepted is False
    assert result.standing is Standing.BLOCKED
    assert result.receipt.reason == "PROVIDER_ERROR:ValueError"

    observation = await gym.observe(episode_id)
    assert observation.state["facts"] == []

    await gym.teardown(episode_id, authority_ref=AUTHORITY)


async def test_re_establishing_an_already_established_capability_is_refused() -> None:
    gym, episode_id = await _materialize_authorized()

    first = await _establish(gym, episode_id)
    assert first.accepted is True, first.receipt.reason

    second = await _establish(gym, episode_id)

    assert second.accepted is False
    assert second.standing is Standing.BLOCKED
    assert second.receipt.reason == "PROVIDER_ERROR:ValueError"

    observation = await gym.observe(episode_id)
    assert observation.state["facts"] == ["capability:architecture-established"]

    await gym.teardown(episode_id, authority_ref=AUTHORITY)


async def test_do_capability_is_refused_without_admitted_authority() -> None:
    """A plain GymAct() defaults to DenyAuthorityResolver -- the DO capability
    must be refused, not silently authorized."""
    gym = GymAct()
    gym.register_provider(TogafProvider())
    materialization = await gym.materialize(
        MaterializationIntent(provider="togaf", config={})
    )
    assert materialization.accepted is True, materialization.receipt.reason
    episode_id = materialization.episode.episode_id

    result = await gym.act(
        ActuationIntent(episode_id=episode_id, capability=CAPABILITY_ESTABLISH)
    )

    assert result.accepted is False
    assert result.standing is Standing.REFUSED

    await gym.teardown(episode_id)


async def test_unknown_requirement_subject_is_refused() -> None:
    gym, episode_id = await _materialize_authorized()

    establish_result = await _establish(gym, episode_id)
    assert establish_result.accepted is True, establish_result.receipt.reason

    result = await _submit(gym, episode_id, "not-a-real-requirement")

    assert result.accepted is False
    assert result.receipt.reason == "PROVIDER_ERROR:ValueError"

    observation = await gym.observe(episode_id)
    assert observation.state["facts"] == ["capability:architecture-established"]

    await gym.teardown(episode_id, authority_ref=AUTHORITY)
