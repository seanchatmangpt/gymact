from __future__ import annotations

import pytest

from gymact.gyms.commerce_dfcm_gym import (
    COMMERCE_DFCM_CAPABILITIES,
    CommerceDfcmProvider,
)


def capability(binding: str):
    return next(item for item in COMMERCE_DFCM_CAPABILITIES if item.binding == binding)


def agreement(authority: str) -> dict[str, object]:
    return {
        "agreement_id": "agreement-authority-fence",
        "legal_entity_id": "legal-fortune5",
        "account_id": "account-fortune5",
        "product_id": "chatman-ecosystem",
        "offer_id": "offer-selected",
        "billing_authority": authority,
        "pricing": [
            {"dimension_id": "calls", "unit": "call", "unit_price_micros": 7}
        ],
        "effective_at": "2026-08-19T00:00:00Z",
    }


@pytest.mark.asyncio
async def test_billing_authority_fence_refuses_second_authority_for_same_agreement() -> None:
    env = await CommerceDfcmProvider().materialize(scenario="fortune-5-commerce", config={})

    first = await env.actuate(
        capability("agreement.admit"),
        {"agreement": agreement("EXTERNAL_COMMERCE")},
    )
    assert first["standing"] == "ALIVE"

    conflict = await env.actuate(
        capability("billing-authority.fence"),
        {"agreement": agreement("DIRECT")},
    )
    assert conflict["standing"] == "REFUSED"
    assert conflict["refusal"]["code"] == "REFUSED:MULTIPLE_BILLING_AUTHORITIES"

    state = await env.observe()
    assert state["agreement_ids"] == ["agreement-authority-fence"]
    assert env.world.agreements["agreement-authority-fence"].billing_authority.value == (
        "EXTERNAL_COMMERCE"
    )
