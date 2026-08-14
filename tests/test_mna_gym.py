from __future__ import annotations

from gymact.gyms.mna import build_mna_provider
from gymact.mna import (
    MnaSelectedPlan,
    execute_fortune5_mna_simulation,
    fortune5_mna_agent_space,
    fortune5_mna_space,
)
from gymact.models import Standing


SELECTED = MnaSelectedPlan(
    transaction_form="stock_purchase",
    consideration="mixed",
    integration_topology="federate",
    operating_model="business_unit",
    separation_strategy="transitional_services",
    regulatory_sequence="clear_then_sign",
)


def test_mna_pack_compiles_ten_ordered_transaction_stages() -> None:
    provider = build_mna_provider()
    tasks = provider.tasks()

    assert len(tasks) == 10
    assert tasks[0].identifier == "mna.00.strategic-thesis"
    assert tasks[-1].identifier == "mna.90.simulated-close"
    assert tasks[-1].family == "simulated-close"
    assert tasks[-2].family == "governance"
    assert len(tasks[2].subjects) == 5


def test_mna_dfcm_frontiers_are_preserved_before_execution() -> None:
    transactions = fortune5_mna_space()
    agents = fortune5_mna_agent_space()

    assert transactions.total_cardinality == 729
    assert transactions.truncated is False
    assert agents.total_cardinality == 216
    assert agents.truncated is False


async def test_fortune5_mna_executes_with_zero_llms_and_receipted_close() -> None:
    result = await execute_fortune5_mna_simulation(SELECTED)

    assert result.standing is Standing.ALIVE
    assert result.verified is True
    assert result.llm_calls == 0
    assert result.transaction_frontier_cardinality == 729
    assert result.agent_frontier_cardinality == 216
    assert len(result.facts) == 14
    assert len(result.manufactured_agent_receipts) == 14
    assert result.standard_close_refusal_receipt_id in result.receipt_ids
    assert result.simulated_close_receipt_id in result.receipt_ids
    assert result.standard_close_refusal_receipt_id != result.simulated_close_receipt_id
    assert result.external_transaction_attempted is False
    assert result.external_transaction_reason == "NO_EXTERNAL_TRANSACTION_PORT"
