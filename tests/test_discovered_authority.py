"""Chicago-style: `GenericDiscoveredProvider`/`DiscoveredEnvironment` with
`requires_authority=True`, driven through a real `GymAct` episode against a
real subprocess. Every subject attempted earlier this session used the
default `requires_authority=False`, so authority-gating on this provider had
zero test coverage. Closes that gap using the same pattern as
`test_cube_container_counter.py`'s `test_authority_refusal_does_not_change_real_cube_state`:
real `DenyAuthorityResolver` (fail-closed default) and real
`AllowListAuthorityResolver`, real `subprocess.run` underneath, real state
(not interaction) assertions.
"""

from __future__ import annotations

from gymact import GymAct, MaterializationIntent
from gymact.authority import AllowListAuthorityResolver
from gymact.gyms.discovered import GenericDiscoveredProvider
from gymact.models import ActuationIntent, Standing

RUN_CAPABILITY = "urn:gymact:discovered:capability:run"

_RECIPE_CONFIG = {
    "subject": "authority-gated-echo",
    "command": ["python3", "-c", "print('ok')"],
    "cwd": "/tmp",
    "timeout_seconds": 10.0,
    "success_markers": ["ok"],
    "requires_authority": True,
}


async def test_default_deny_resolver_refuses_authority_gated_discovered_act() -> None:
    """No resolver injected -> GymAct falls back to the fail-closed
    DenyAuthorityResolver. The real subprocess must never run."""
    gym = GymAct()
    gym.register_provider(GenericDiscoveredProvider())

    materialization = await gym.materialize(
        MaterializationIntent(provider="discovered", config=dict(_RECIPE_CONFIG))
    )
    assert materialization.accepted is True
    episode_id = materialization.episode.episode_id

    result = await gym.act(ActuationIntent(episode_id=episode_id, capability=RUN_CAPABILITY))

    assert result.accepted is False
    assert result.standing == Standing.REFUSED
    assert result.receipt.reason == "LIVE_AUTHORITY_REQUIRED"

    await gym.teardown(episode_id)


async def test_authority_refusal_does_not_change_real_discovered_state() -> None:
    """Mirrors the cube-container-counter reference test: prove the real
    subprocess never actually ran by observing real environment state
    before and after a refused act()."""
    gym = GymAct()
    gym.register_provider(GenericDiscoveredProvider())

    materialization = await gym.materialize(
        MaterializationIntent(provider="discovered", config=dict(_RECIPE_CONFIG))
    )
    episode_id = materialization.episode.episode_id

    before = await gym.observe(episode_id)
    assert before.state["attempted"] is False
    assert before.state["returncode"] is None

    result = await gym.act(ActuationIntent(episode_id=episode_id, capability=RUN_CAPABILITY))
    assert result.accepted is False

    after = await gym.observe(episode_id)
    assert after.state == before.state
    assert after.state["attempted"] is False
    assert after.state["stdout"] == ""
    assert after.state["returncode"] is None

    await gym.teardown(episode_id)


async def test_allowlist_resolver_admits_matching_authority_ref_and_real_subprocess_runs() -> None:
    """A resolver that explicitly admits a matching authority_ref lets the
    real subprocess run for real; observe its real stdout/returncode."""
    resolver = AllowListAuthorityResolver({"urn:gymact:authority:ops-team"})
    gym = GymAct(authority_resolver=resolver)
    gym.register_provider(GenericDiscoveredProvider())

    materialization = await gym.materialize(
        MaterializationIntent(provider="discovered", config=dict(_RECIPE_CONFIG))
    )
    episode_id = materialization.episode.episode_id

    result = await gym.act(
        ActuationIntent(
            episode_id=episode_id,
            capability=RUN_CAPABILITY,
            authority_ref="urn:gymact:authority:ops-team",
        )
    )

    assert result.accepted is True
    assert result.standing == Standing.ALIVE
    assert result.receipt.authority_evidence_ref == (
        "urn:gymact:authority-decision:urn:gymact:authority:ops-team"
    )

    observed = await gym.observe(episode_id)
    assert observed.state["attempted"] is True
    assert observed.state["returncode"] == 0
    assert observed.state["stdout"].strip() == "ok"
    assert observed.state["solved"] is True

    await gym.teardown(episode_id)


async def test_allowlist_resolver_refuses_non_matching_authority_ref() -> None:
    """A real allowlist that does not contain the presented authority_ref
    refuses, and the real subprocess never runs -- exact allowlist
    matching is not fuzzy or prefix-based."""
    resolver = AllowListAuthorityResolver({"urn:gymact:authority:ops-team"})
    gym = GymAct(authority_resolver=resolver)
    gym.register_provider(GenericDiscoveredProvider())

    materialization = await gym.materialize(
        MaterializationIntent(provider="discovered", config=dict(_RECIPE_CONFIG))
    )
    episode_id = materialization.episode.episode_id

    result = await gym.act(
        ActuationIntent(
            episode_id=episode_id,
            capability=RUN_CAPABILITY,
            authority_ref="urn:gymact:authority:not-on-the-list",
        )
    )

    assert result.accepted is False
    assert result.standing == Standing.REFUSED
    assert result.receipt.reason == "AUTHORITY_NOT_ADMITTED"

    observed = await gym.observe(episode_id)
    assert observed.state["attempted"] is False

    await gym.teardown(episode_id)
