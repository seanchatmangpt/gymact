from __future__ import annotations

import pytest

from gymact.authority import AllowListAuthorityResolver
from gymact.kernel import GymAct
from gymact.models import ActuationIntent, Standing
from gymact.registry import create_builtin_provider


def agreement() -> dict[str, object]:
    return {
        "agreement_id": "agreement-runtime",
        "legal_entity_id": "legal-runtime",
        "account_id": "account-runtime",
        "product_id": "product-runtime",
        "offer_id": "offer-runtime",
        "billing_authority": "EXTERNAL_COMMERCE",
        "pricing": [
            {"dimension_id": "calls", "unit": "call", "unit_price_micros": 11}
        ],
        "effective_at": "2026-08-19T00:00:00Z",
    }


def agreement_capability(gym: GymAct, episode_id: str):
    return next(
        capability
        for capability in gym.capabilities(episode_id)
        if capability.binding == "agreement.admit"
    )


@pytest.mark.asyncio
async def test_registered_provider_is_discoverable_and_default_runtime_refuses_do() -> None:
    gym = GymAct()
    gym.register_provider(create_builtin_provider("commerce-dfcm"))
    assert "commerce-dfcm" in gym.discover()

    materialized = await gym.create_episode("commerce-dfcm", scenario="provider-neutral")
    assert materialized.accepted
    assert materialized.episode is not None
    episode_id = materialized.episode.episode_id
    capability = agreement_capability(gym, episode_id)

    refused = await gym.act(
        ActuationIntent(
            episode_id=episode_id,
            capability=capability.iri,
            payload={"agreement": agreement()},
            idempotency_key="runtime-deny",
        )
    )
    assert not refused.accepted
    assert refused.standing is Standing.REFUSED
    assert refused.receipt.reason == "LIVE_AUTHORITY_REQUIRED"
    assert (await gym.observe(episode_id)).state["agreement_ids"] == []
    await gym.teardown(episode_id)


@pytest.mark.asyncio
async def test_registered_provider_executes_with_outer_authority_and_verifies_state() -> None:
    gym = GymAct(
        authority_resolver=AllowListAuthorityResolver({"authority:commerce-test"})
    )
    gym.register_provider(create_builtin_provider("commerce-dfcm"))

    materialized = await gym.create_episode("commerce-dfcm", scenario="fortune-5-commerce")
    assert materialized.accepted
    assert materialized.episode is not None
    episode_id = materialized.episode.episode_id
    capability = agreement_capability(gym, episode_id)

    result = await gym.act(
        ActuationIntent(
            episode_id=episode_id,
            capability=capability.iri,
            payload={"agreement": agreement()},
            authority_ref="authority:commerce-test",
            idempotency_key="runtime-admit",
        )
    )
    assert result.accepted
    assert result.standing is Standing.ALIVE
    assert result.receipt.authority_evidence_ref
    assert result.effect is not None
    assert result.effect["standing"] == "ALIVE"
    assert result.effect["evidence"]["receipt_id"]

    verification = await gym.verify(
        episode_id, {"agreement_ids": ["agreement-runtime"]}
    )
    assert verification.passed
    receipts = gym.episode_receipts(episode_id)
    assert any(receipt.verified is True for receipt in receipts)
    await gym.teardown(episode_id)
