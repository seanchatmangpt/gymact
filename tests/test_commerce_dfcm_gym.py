from __future__ import annotations

import pytest

from gymact.gyms.commerce_dfcm import CAPABILITIES
from gymact.gyms.commerce_dfcm_gym import (
    COMMERCE_DFCM_CAPABILITIES,
    COMMERCE_DFCM_EXTERNAL_FRONTIER,
    COMMERCE_DFCM_SEMANTIC_CAPABILITIES,
    CommerceDfcmProvider,
)


def cap(binding: str):
    return next(item for item in COMMERCE_DFCM_CAPABILITIES if item.binding == binding)


def semantic_cap(binding: str):
    return next(
        item for item in COMMERCE_DFCM_SEMANTIC_CAPABILITIES if item.binding == binding
    )


def grant(subject: str, operation: str) -> dict[str, str]:
    return {
        "grant_id": f"grant:{subject}:{operation}",
        "authority": "brce:test",
        "subject_id": subject,
        "allowed_operation": operation,
        "evidence_ref": "urn:test:authority",
    }


def agreement() -> dict[str, object]:
    return {
        "agreement_id": "agreement-1",
        "legal_entity_id": "legal-1",
        "account_id": "account-1",
        "product_id": "product-1",
        "offer_id": "offer-1",
        "billing_authority": "EXTERNAL_COMMERCE",
        "pricing": [
            {"dimension_id": "calls", "unit": "call", "unit_price_micros": 7}
        ],
        "effective_at": "2026-08-19T00:00:00Z",
    }


def event(kind: str, revision: int, event_id: str) -> dict[str, object]:
    return {
        "event_id": event_id,
        "source": "external",
        "kind": kind,
        "agreement_id": "agreement-1",
        "entitlement_id": "entitlement-1",
        "tenant_id": "tenant-1",
        "product_id": "product-1",
        "revision": revision,
        "quantity": 1,
        "capabilities": ["api"],
        "support_tier": "enterprise-247",
    }


@pytest.mark.asyncio
async def test_provider_separates_32_semantic_capabilities_from_25_executable() -> None:
    provider = CommerceDfcmProvider()
    env = await provider.materialize(scenario="provider-neutral", config={})
    semantic = tuple(item.binding for item in env.semantic_capabilities())
    executable = tuple(item.binding for item in env.capabilities())
    external = tuple(item.binding for item in env.external_frontier())

    assert len(semantic) == 32
    assert set(semantic) == {item.capability_id for item in CAPABILITIES}
    assert len(semantic) == len(set(semantic))
    assert len(executable) == 25
    assert len(external) == 7
    assert set(executable).isdisjoint(external)
    assert set(executable) | set(external) == set(semantic)
    assert tuple(COMMERCE_DFCM_EXTERNAL_FRONTIER) == env.external_frontier()


@pytest.mark.asyncio
async def test_provider_executes_internal_commerce_pipeline_and_receipts_every_stage() -> None:
    env = await CommerceDfcmProvider().materialize(scenario=None, config={})

    admitted = await env.actuate(cap("agreement.admit"), {"agreement": agreement()})
    assert admitted["standing"] == "ALIVE"
    assert admitted["evidence"]["receipt_id"]

    created = await env.actuate(
        cap("entitlement.apply-event"),
        {
            "source": "external",
            "event": event("CREATE", 1, "event-1"),
            "grant": grant("entitlement-1", "entitlement.apply-event"),
        },
    )
    assert created["standing"] == "ALIVE"

    activated = await env.actuate(
        cap("entitlement.lifecycle"),
        {
            "source": "external",
            "event": event("ACTIVATE", 2, "event-2"),
            "grant": grant("entitlement-1", "entitlement.apply-event"),
        },
    )
    assert activated["standing"] == "ALIVE"

    observed = await env.actuate(
        cap("usage.observe"),
        {
            "observation": {
                "observation_id": "usage-1",
                "entitlement_id": "entitlement-1",
                "tenant_id": "tenant-1",
                "dimension_id": "calls",
                "quantity": 3,
                "observed_at": "2026-08-19T00:01:00Z",
            }
        },
    )
    assert observed["standing"] == "ALIVE"

    usage = await env.actuate(cap("usage.admit"), {"observation_id": "usage-1"})
    assert usage["subject"]["admitted"] is True

    meter = await env.actuate(
        cap("meter.construct"),
        {"intent_id": "meter-1", "observation_ids": ["usage-1"]},
    )
    assert meter["subject"]["amount_micros"] == 21

    support = await env.actuate(
        cap("support.entitle"), {"entitlement_id": "entitlement-1"}
    )
    assert support["subject"]["support_tier"] == "enterprise-247"

    packaging = {
        "helm_chart": True,
        "stable_kubernetes_apis": True,
        "sbom": True,
        "vulnerability_scan": True,
        "signed_provenance": True,
        "portable_registry_artifact": True,
    }
    admitted_packaging = await env.actuate(
        cap("packaging.helm"), {"packaging": packaging}
    )
    assert admitted_packaging["standing"] == "ALIVE"

    state = await env.observe()
    assert state["agreement_ids"] == ["agreement-1"]
    assert state["entitlement_ids"] == ["entitlement-1"]
    assert state["meter_intent_ids"] == ["meter-1"]
    assert state["packaging_admitted"] is True
    assert state["semantic_capability_count"] == 32
    assert state["executable_capability_count"] == 25
    assert state["external_frontier_count"] == 7
    assert state["receipt_count"] >= 7


@pytest.mark.asyncio
async def test_external_do_is_semantic_frontier_and_fixture_cannot_become_acceptance() -> None:
    env = await CommerceDfcmProvider().materialize(scenario=None, config={})

    assert "meter.submit" not in {item.binding for item in env.capabilities()}
    external = await env.actuate(
        semantic_cap("meter.submit"), {"intent_id": "anything"}
    )
    assert external["standing"] == "REFUSED"
    assert external["refusal"]["code"] == "REFUSED:EXTERNAL_DO_WITHOUT_AUTHORITY"

    await env.actuate(cap("agreement.admit"), {"agreement": agreement()})
    await env.actuate(
        cap("entitlement.apply-event"),
        {
            "event": event("CREATE", 1, "event-1"),
            "grant": grant("entitlement-1", "entitlement.apply-event"),
        },
    )
    await env.actuate(
        cap("entitlement.lifecycle"),
        {
            "event": event("ACTIVATE", 2, "event-2"),
            "grant": grant("entitlement-1", "entitlement.apply-event"),
        },
    )
    await env.actuate(
        cap("usage.observe"),
        {
            "observation_id": "usage-1",
            "entitlement_id": "entitlement-1",
            "tenant_id": "tenant-1",
            "dimension_id": "calls",
            "quantity": 1,
            "observed_at": "2026-08-19T00:01:00Z",
        },
    )
    await env.actuate(cap("usage.admit"), {"observation_id": "usage-1"})
    await env.actuate(
        cap("meter.construct"),
        {"intent_id": "meter-1", "observation_ids": ["usage-1"]},
    )

    fixture = await env.actuate(
        cap("provider.acceptance.admit"),
        {
            "acceptance_id": "acceptance-1",
            "intent_id": "meter-1",
            "provider": "fixture",
            "observed": True,
            "evidence_ref": "urn:fixture:acceptance",
            "accepted_quantity": 1,
            "evidence_origin": "FIXTURE",
        },
    )
    assert fixture["standing"] == "REFUSED"
    assert fixture["refusal"]["code"] == "REFUSED:PROVIDER_ACCEPTANCE_NOT_OBSERVED"


@pytest.mark.asyncio
async def test_checkpoint_restore_is_reversible_inside_the_bounded_world() -> None:
    env = await CommerceDfcmProvider().materialize(scenario=None, config={})
    checkpoint = await env.checkpoint()
    await env.actuate(cap("agreement.admit"), {"agreement": agreement()})
    assert (await env.observe())["agreement_ids"] == ["agreement-1"]

    await env.restore(checkpoint)
    assert (await env.observe())["agreement_ids"] == []
