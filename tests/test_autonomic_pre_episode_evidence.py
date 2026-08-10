import pytest

from gymact.authority import AllowListAuthorityResolver
from gymact.autonomic import AutonomicController, ConsequenceRequest
from gymact.models import Standing
from gymact.providers import MemoryProvider
from gymact.runtime import ProductionGymAct

AUTHORITY = "urn:test:authority:autonomic-pre-episode"


@pytest.mark.asyncio
async def test_pre_episode_materialization_refusal_retains_real_receipt_in_knowledge() -> None:
    runtime = ProductionGymAct(
        validate_profile=True,
        authority_resolver=AllowListAuthorityResolver({AUTHORITY}),
    )
    runtime.register_provider(MemoryProvider())
    controller = AutonomicController(runtime)

    outcome = await controller.run(
        ConsequenceRequest(
            request_id="unknown-provider",
            provider="unregistered-provider",
            capability_binding="run",
            payload={"value": 1},
            expected={"done": True},
            authority_ref=AUTHORITY,
            idempotency_key="idem:unknown-provider",
        )
    )

    assert outcome.standing is Standing.UNSUPPORTED
    assert outcome.episode_id is None
    assert outcome.receipt_ids
    assert outcome.knowledge.evidence_refs == outcome.receipt_ids
    assert outcome.phase_records[0].evidence_refs == outcome.receipt_ids
    assert runtime.ledger.find(outcome.receipt_ids[0]) is not None
