from __future__ import annotations

import asyncio

from gymact import GymAct
from gymact.authority import AllowListAuthorityResolver
from gymact.gyms.world_cyber import build_world_cyber_provider
from gymact.models import ActuationIntent, MaterializationIntent, Standing

AUTHORITY = "urn:gymact:authority:world-cyber-spy-vs-spy-test"
WORLD_ID = "spy-vs-spy-shared-world"
RED_INTERRUPT = "urn:gymact:world-cyber:cap:interrupt-identity"
BLUE_RESTORE = "urn:gymact:world-cyber:cap:restore-resource"


def run(coro):
    return asyncio.run(coro)


def materialize(gym: GymAct, actor: str) -> str:
    result = run(
        gym.materialize(
            MaterializationIntent(
                provider="world-cyber",
                config={"actor": actor, "world_id": WORLD_ID},
            )
        )
    )
    assert result.accepted is True, result.receipt.reason
    assert result.episode is not None
    return result.episode.episode_id


def test_spy_vs_spy_actor_episodes_actuate_one_shared_world() -> None:
    provider = build_world_cyber_provider()
    gym = GymAct(authority_resolver=AllowListAuthorityResolver({AUTHORITY}))
    gym.register_provider(provider)

    red = materialize(gym, "red")
    blue = materialize(gym, "blue")
    observer = materialize(gym, "observer")

    assert {cap.binding for cap in gym.capabilities(red)} == {
        "degrade-service",
        "exhaust-quota",
        "interrupt-identity",
        "partition-network",
    }
    assert {cap.binding for cap in gym.capabilities(blue)} == {
        "failover-service",
        "isolate-resource",
        "reroute-service",
        "restore-resource",
    }
    assert gym.capabilities(observer) == ()

    red_result = run(
        gym.act(
            ActuationIntent(
                episode_id=red,
                capability=RED_INTERRUPT,
                payload={"target": "identity-core"},
                authority_ref=AUTHORITY,
            )
        )
    )
    assert red_result.accepted is True
    assert red_result.standing is Standing.ALIVE
    assert red_result.effect is not None
    assert red_result.effect["world_id"] == WORLD_ID
    assert red_result.receipt.authority_evidence_ref is not None

    # Blue sees the same world through a one-step-stale telemetry surface.
    blue_observation = run(gym.observe(blue)).state
    assert blue_observation["world_id"] == WORLD_ID
    assert blue_observation["world_step"] == 1
    assert blue_observation["observed_step"] == 0
    assert blue_observation["assets"]["identity-core"] == "healthy"

    # The scoring-only observer has zero DO capabilities and zero telemetry lag.
    truth = run(gym.observe(observer)).state
    assert truth["world_step"] == 1
    assert truth["observed_step"] == 1
    assert truth["assets"]["identity-core"] == "unavailable"
    assert truth["assets"]["hospital-ops"] == "degraded"

    blue_result = run(
        gym.act(
            ActuationIntent(
                episode_id=blue,
                capability=BLUE_RESTORE,
                payload={"target": "identity-core"},
                authority_ref=AUTHORITY,
            )
        )
    )
    assert blue_result.accepted is True
    assert blue_result.standing is Standing.ALIVE
    assert blue_result.effect is not None
    assert blue_result.effect["world_id"] == WORLD_ID

    truth = run(gym.observe(observer)).state
    assert truth["world_step"] == 2
    assert truth["assets"]["identity-core"] == "healthy"
    assert truth["assets"]["hospital-ops"] == "healthy"

    assert gym.episode_receipts(red)[-1] == red_result.receipt
    assert gym.episode_receipts(blue)[-1] == blue_result.receipt
