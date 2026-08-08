from __future__ import annotations

import pytest

from gymact.authority import AllowListAuthorityResolver
from gymact.models import ActuationIntent, MaterializationIntent, Standing
from gymact.providers import MemoryProvider
from gymact.runtime import ProductionGymAct

AUTHORITY = "urn:test:authority"
CAPABILITY = "urn:gymact:memory:capability:set"


@pytest.mark.asyncio
async def test_private_production_do_port_refuses_wrong_broker_seal() -> None:
    runtime = ProductionGymAct(
        authority_resolver=AllowListAuthorityResolver({AUTHORITY})
    )
    runtime.register_provider(MemoryProvider())
    materialized = await runtime.materialize(
        MaterializationIntent(
            provider="memory",
            config={"initial": {"x": 1}, "requires_authority": True},
            idempotency_key="sealed-materialize",
        )
    )
    assert materialized.episode is not None
    episode_id = materialized.episode.episode_id
    refused = await runtime._act_from_brce(
        ActuationIntent(
            episode_id=episode_id,
            capability=CAPABILITY,
            payload={"key": "x", "value": 2},
            authority_ref=AUTHORITY,
            idempotency_key="wrong-seal",
        ),
        seal=object(),
    )
    assert refused.standing is Standing.REFUSED
    assert refused.receipt.reason == "BRCE_EXECUTION_SEAL_REFUSED"
    assert (await runtime.observe(episode_id)).state == {"x": 1}
