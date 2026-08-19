from __future__ import annotations

import pytest

from gymact.commerce_dfcm import (
    CommerceSelectedPlan,
    commerce_agent_space,
    commerce_design_space,
    execute_commerce_dfcm,
)
from gymact.models import Standing


def selected_plan(*, concurrent: bool = False) -> CommerceSelectedPlan:
    return CommerceSelectedPlan(
        billing_authority="EXTERNAL_COMMERCE",
        pricing_model="hybrid",
        entitlement_cardinality="concurrent" if concurrent else "single",
        identity_binding="account",
        usage_projection="hybrid",
        packaging_topology="helm-first",
        supply_chain_policy="strict",
        support_tier="enterprise-247",
    )


def test_commerce_dfcm_preserves_full_reversible_design_and_agent_frontiers() -> None:
    design = commerce_design_space()
    agents = commerce_agent_space()

    assert design.total_cardinality == 2592
    assert len(design.combinations) == 2592
    assert not design.truncated
    assert agents.total_cardinality == 216
    assert len(agents.combinations) == 216
    assert not agents.truncated

    bounded = commerce_design_space(max_combinations=100)
    assert bounded.total_cardinality == 2592
    assert len(bounded.combinations) == 100
    assert bounded.truncated


@pytest.mark.asyncio
@pytest.mark.parametrize("concurrent", [False, True])
async def test_post_agi_dfcm_executes_every_internal_capability_and_stops_at_marketplace(
    concurrent: bool,
) -> None:
    result = await execute_commerce_dfcm(selected_plan(concurrent=concurrent))

    assert result.standing is Standing.ALIVE
    assert result.internal_standing is Standing.ALIVE
    assert result.external_standing is Standing.BLOCKED
    assert result.verified
    assert result.design_frontier_cardinality == 2592
    assert result.agent_frontier_cardinality == 216
    assert result.semantic_capability_count == 32
    assert result.executable_capability_count == 25
    assert result.external_frontier_count == 7
    assert len(set(result.executed_alive_bindings)) == 22
    assert set(result.exercised_refusal_bindings) == {
        "provider.acceptance.admit",
        "replay.idempotent",
        "settlement.reconcile",
    }
    assert set(result.external_frontier_bindings) == {
        "meter.submit",
        "external.seller-registration",
        "external.kyc",
        "external.tax",
        "external.banking",
        "external.eula",
        "external.provider-review",
    }
    assert result.llm_calls == 0
    assert result.marketplace_attempted is False
    assert result.manufactured_agent_receipts
    assert result.runtime_receipt_ids
