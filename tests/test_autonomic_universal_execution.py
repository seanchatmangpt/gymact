from pathlib import Path

import pytest

from gymact.authority import AllowListAuthorityResolver
from gymact.autonomic import (
    AutonomicController,
    AutonomicPhase,
    BoundedGrantIssuer,
    ConsequenceRequest,
    FailureClass,
)
from gymact.automation import AutonomicAutomation, AutomationPolicy
from gymact.catalog import ProviderSource, default_provider_catalog
from gymact.gyms.vendor_benchmarks import VENDOR_SPECS
from gymact.models import ActuationIntent, Standing
from gymact.providers import MEMORY_CAPABILITIES, MemoryProvider
from gymact.registry import builtin_provider_names
from gymact.runtime import ProductionGymAct


AUTHORITY = "urn:test:authority:autonomic"


def _runtime() -> ProductionGymAct:
    runtime = ProductionGymAct(
        validate_profile=True,
        authority_resolver=AllowListAuthorityResolver({AUTHORITY}),
    )
    runtime.register_provider(MemoryProvider())
    return runtime


def _request(request_id: str, amount: int = 2) -> ConsequenceRequest:
    return ConsequenceRequest(
        request_id=request_id,
        provider="memory",
        config={"initial": {"counter": 0}, "requires_authority": True},
        capability_binding="increment",
        payload={"key": "counter", "amount": amount},
        expected={"counter": amount},
        authority_ref=AUTHORITY,
        idempotency_key=f"idem:{request_id}",
    )


@pytest.mark.asyncio
async def test_production_direct_act_is_refused_but_autonomic_brce_path_is_verified() -> None:
    runtime = _runtime()
    direct_world = await runtime.create_episode(
        "memory",
        config={"initial": {"counter": 0}, "requires_authority": True},
        authority_ref=AUTHORITY,
        idempotency_key="direct:materialize",
    )
    assert direct_world.accepted
    assert direct_world.episode is not None

    direct = await runtime.act(
        ActuationIntent(
            episode_id=direct_world.episode.episode_id,
            capability=MEMORY_CAPABILITIES[2].iri,
            payload={"key": "counter", "amount": 9},
            authority_ref=AUTHORITY,
            idempotency_key="direct:act",
        )
    )
    assert direct.standing is Standing.REFUSED
    assert direct.receipt.reason == "BRCE_EXECUTION_GRANT_REQUIRED"
    await runtime.teardown(direct_world.episode.episode_id, authority_ref=AUTHORITY)

    controller = AutonomicController(
        runtime,
        grant_issuer=BoundedGrantIssuer({AUTHORITY}),
    )
    outcome = await controller.run(_request("verified"))

    assert outcome.standing is Standing.ALIVE
    assert outcome.verified
    assert outcome.knowledge.failure_class is FailureClass.NONE
    assert outcome.knowledge.world_changed is True
    assert outcome.cleanup_standing is Standing.ALIVE
    assert tuple(record.phase for record in outcome.phase_records) == (
        AutonomicPhase.MONITOR,
        AutonomicPhase.ANALYZE,
        AutonomicPhase.PLAN,
        AutonomicPhase.EXECUTE,
        AutonomicPhase.KNOWLEDGE,
    )
    assert outcome.receipt_ids


@pytest.mark.asyncio
async def test_missing_grant_issuer_refuses_before_do_and_records_zero_act_receipts() -> None:
    runtime = _runtime()
    controller = AutonomicController(runtime)
    outcome = await controller.run(_request("no-grant"))

    assert outcome.standing is Standing.REFUSED
    assert outcome.reason == "EXECUTION_GRANT_ISSUER_REQUIRED"
    assert outcome.knowledge.failure_class is FailureClass.AUTHORITY
    receipts = runtime.episode_receipts(outcome.episode_id or "")
    assert all(receipt.idempotency_key != "idem:no-grant" for receipt in receipts)


@pytest.mark.asyncio
async def test_bounded_automation_executes_multiple_isolated_worlds_concurrently() -> None:
    runtime = _runtime()
    controller = AutonomicController(
        runtime,
        grant_issuer=BoundedGrantIssuer({AUTHORITY}),
    )
    automation = AutonomicAutomation(
        controller,
        policy=AutomationPolicy(max_concurrency=2, max_requests=4),
    )

    result = await automation.run((_request("a", 1), _request("b", 3)))

    assert result.all_verified
    assert result.verified_count == 2
    assert result.standing_counts == {Standing.ALIVE.value: 2}
    assert [outcome.request_id for outcome in result.outcomes] == ["a", "b"]
    assert len({outcome.episode_id for outcome in result.outcomes}) == 2


@pytest.mark.asyncio
async def test_automation_refuses_unbounded_batch_before_execution() -> None:
    runtime = _runtime()
    automation = AutonomicAutomation(
        AutonomicController(runtime, grant_issuer=BoundedGrantIssuer({AUTHORITY})),
        policy=AutomationPolicy(max_concurrency=1, max_requests=1),
    )
    with pytest.raises(ValueError, match="AUTOMATION_REQUEST_LIMIT_EXCEEDED"):
        await automation.run((_request("a"), _request("b")))


def test_default_catalog_represents_entire_exact_pinned_vendor_corpus_without_execution() -> None:
    catalog = default_provider_catalog()

    assert len(catalog.names()) == len(VENDOR_SPECS) + len(builtin_provider_names())
    for benchmark in ("agentbench", "osworld", "swe-bench", "webarena", "workarena"):
        descriptor = catalog.describe(benchmark)
        assert descriptor.source is ProviderSource.VENDOR_BENCHMARK
        assert descriptor.revision == VENDOR_SPECS[benchmark].revision
    assert catalog.describe("memory").source is ProviderSource.BUILTIN


def test_vendor_readiness_reports_real_missing_checkout_as_blocked(tmp_path: Path) -> None:
    catalog = default_provider_catalog()
    readiness = catalog.readiness("agentbench", lab_root=tmp_path)

    assert readiness.standing is Standing.BLOCKED
    assert readiness.reason == "BLOCKED:VENDOR_CHECKOUT_MISSING"
    assert not readiness.ready_for_materialization_attempt
