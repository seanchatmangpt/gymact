from __future__ import annotations

import asyncio

import pytest

from gymact import GymAct
from gymact.authority import AllowListAuthorityResolver, DenyAuthorityResolver
from gymact.gyms.world_cyber import build_world_cyber_provider
from gymact.models import ActuationIntent, MaterializationIntent, Standing

AUTHORITY = "urn:gymact:authority:world-cyber-test"
RED_INTERRUPT = "urn:gymact:world-cyber:cap:interrupt-identity"


def run(coro):
    return asyncio.run(coro)


def capability(env, binding: str):
    return next(item for item in env.capabilities() if item.binding == binding)


def materialized_gym(authority_resolver) -> tuple[GymAct, str]:
    gym = GymAct(authority_resolver=authority_resolver)
    gym.register_provider(build_world_cyber_provider())
    result = run(
        gym.materialize(
            MaterializationIntent(provider="world-cyber", config={"actor": "red"})
        )
    )
    assert result.accepted is True, result.receipt.reason
    assert result.episode is not None
    return gym, result.episode.episode_id


def test_catalog_is_graph_native_and_actor_scoped() -> None:
    provider = build_world_cyber_provider()
    catalog = provider.catalog()
    assert len(catalog.assets) == 7
    assert len(catalog.capabilities) == 9
    assert set(catalog.actor_actions) == {"blue", "red", "gray", "observer"}
    assert catalog.actor_actions["observer"] == ()
    assert catalog.max_depth == 6
    assert catalog.max_events == 64
    assert catalog.max_impacted_resources == 32
    assert catalog.actor_lag_steps == {"blue": 1, "gray": 1, "observer": 0, "red": 2}


def test_red_surface_is_synthetic_only_and_cannot_target_outside_world() -> None:
    env = run(build_world_cyber_provider().materialize(scenario=None, config={"actor": "red"}))
    assert {item.binding for item in env.capabilities()} == {
        "degrade-service",
        "exhaust-quota",
        "interrupt-identity",
        "partition-network",
    }
    with pytest.raises(ValueError, match="TARGET_OUTSIDE_MATERIALIZED_WORLD_REFUSED"):
        run(env.actuate(capability(env, "degrade-service"), {"target": "example.com"}))


def test_kernel_refuses_ambient_do_and_receipts_authorized_actuation() -> None:
    denied, denied_episode = materialized_gym(DenyAuthorityResolver())
    refused = run(
        denied.act(
            ActuationIntent(
                episode_id=denied_episode,
                capability=RED_INTERRUPT,
                payload={"target": "identity-core"},
            )
        )
    )
    assert refused.accepted is False
    assert refused.standing is Standing.REFUSED
    assert refused.receipt.reason == "LIVE_AUTHORITY_REQUIRED"
    assert refused.receipt.pre_state_digest == refused.receipt.post_state_digest

    admitted, admitted_episode = materialized_gym(AllowListAuthorityResolver({AUTHORITY}))
    result = run(
        admitted.act(
            ActuationIntent(
                episode_id=admitted_episode,
                capability=RED_INTERRUPT,
                payload={"target": "identity-core"},
                authority_ref=AUTHORITY,
            )
        )
    )
    assert result.accepted is True
    assert result.standing is Standing.ALIVE
    assert result.receipt.authority_ref == AUTHORITY
    assert result.receipt.authority_evidence_ref == (
        f"urn:gymact:authority-decision:{AUTHORITY}"
    )
    assert result.receipt.pre_state_digest != result.receipt.post_state_digest
    assert result.effect is not None
    assert result.effect["procedure"] == "interrupt-identity"
    assert result.effect["target"] == "identity-core"
    assert admitted.episode_receipts(admitted_episode)[-1] == result.receipt


def test_identity_interruption_propagates_across_enterprise_dependencies() -> None:
    red = run(build_world_cyber_provider().materialize(scenario=None, config={"actor": "red"}))
    effect = run(red.actuate(capability(red, "interrupt-identity"), {"target": "identity-core"}))
    assert effect["synthetic_only"] is True
    assert set(effect["changed_assets"]) == {
        "cloud-control",
        "grid-control",
        "hospital-ops",
        "identity-core",
        "payments",
        "warehouse",
    }
    observed = run(red.observe())
    assert observed["world_step"] == 1
    assert observed["observed_step"] == 0
    assert observed["staleness_steps"] == 1
    assert observed["assets"] == {
        "cloud-control": "healthy",
        "payments": "healthy",
        "telecom-backbone": "healthy",
    }


def test_observer_has_truth_without_actuation_surface() -> None:
    observer = run(
        build_world_cyber_provider().materialize(scenario=None, config={"actor": "observer"})
    )
    assert observer.capabilities() == ()
    observed = run(observer.observe())
    assert observed["staleness_steps"] == 0
    assert set(observed["assets"]) == {
        "cloud-control",
        "grid-control",
        "hospital-ops",
        "identity-core",
        "payments",
        "telecom-backbone",
        "warehouse",
    }


def test_blue_restore_recomputes_dependency_state_not_actuator_narration() -> None:
    provider = build_world_cyber_provider()
    red = run(provider.materialize(scenario=None, config={"actor": "red"}))
    run(red.actuate(capability(red, "interrupt-identity"), {"target": "identity-core"}))
    checkpoint = run(red.checkpoint())
    blue = run(provider.materialize(scenario=None, config={"actor": "blue"}))
    blue_checkpoint = run(blue.checkpoint())
    blue_checkpoint["step"] = checkpoint["step"]
    blue_checkpoint["direct"] = checkpoint["direct"]
    blue_checkpoint["effective"] = checkpoint["effective"]
    blue_checkpoint["history"] = checkpoint["history"]
    run(blue.restore(blue_checkpoint))
    result = run(
        blue.actuate(
            capability(blue, "restore-resource"), {"target": "identity-core"}
        )
    )
    assert "identity-core" in result["changed_assets"]
    observed = run(blue.observe())
    assert observed["staleness_steps"] == 1
    assert observed["assets"]["identity-core"] == "unavailable"
    final = run(blue.checkpoint())
    assert final["effective"]["identity-core"] == "healthy"
    assert final["effective"]["hospital-ops"] == "healthy"


def test_checkpoint_restore_is_deterministic() -> None:
    env = run(build_world_cyber_provider().materialize(scenario=None, config={"actor": "gray"}))
    before = run(env.checkpoint())
    run(
        env.actuate(
            capability(env, "cause-region-failure"), {"target": "telecom-backbone"}
        )
    )
    assert run(env.checkpoint()) != before
    run(env.restore(before))
    assert run(env.checkpoint()) == before
