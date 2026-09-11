from __future__ import annotations

from gymact.ggen_agent import (
    compile_ggen_agent_specs,
    load_task_agent_assignments,
)
from gymact.gyms.mna import MNA_PACK_DIR, build_mna_provider
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


def test_mna_logical_organization_is_compiled_from_rdf() -> None:
    specs = compile_ggen_agent_specs(MNA_PACK_DIR)
    assignments = load_task_agent_assignments(MNA_PACK_DIR)

    assert [spec.agent_id for spec in specs] == [
        "mna-diligence",
        "mna-finance",
        "mna-governance",
        "mna-integration",
        "mna-regulatory",
        "mna-strategy",
    ]
    assert all(spec.max_wip == 1 for spec in specs)
    assert all(spec.observation_keys == ("facts", "goal_reached") for spec in specs)
    assert all(spec.output_keys == ("capability", "payload") for spec in specs)
    assert len(assignments) == 10
    assert assignments["mna.20.diligence"] == "mna-diligence"
    assert assignments["mna.90.simulated-close"] == "mna-governance"


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
    assert (
        result.standard_close_refusal_receipt_id
        != result.simulated_close_receipt_id
    )
    assert result.external_transaction_attempted is False
    assert result.external_transaction_reason == "NO_EXTERNAL_TRANSACTION_PORT"


async def test_mna_observed_state_replanning_across_two_chained_episodes() -> None:
    """Gate G08 ('replanning'): a second episode's external SELECT is
    genuinely conditioned on the first episode's real observed final facts,
    not a hardcoded second plan -- matching mna.py's own SELECT-is-external
    law (plan re-selection happens outside GymAct, between two episodes, not
    by mutating the immutable MnaSelectedPlan mid-episode)."""
    from gymact.mna import MnaSelectedPlan as _Plan

    episode_1_plan = _Plan(
        transaction_form="stock_purchase",
        consideration="mixed",
        integration_topology="federate",
        operating_model="business_unit",
        separation_strategy="transitional_services",
        regulatory_sequence="clear_then_sign",
    )
    episode_1 = await execute_fortune5_mna_simulation(episode_1_plan)

    trigger_facts = {
        "urn:gymact:mna:artifact-cyber-diligence",
        "urn:gymact:mna:artifact-technology-diligence",
    }
    observed = set(episode_1.facts)
    assert trigger_facts.issubset(observed), (
        "replan trigger facts must be genuinely present in episode 1's real "
        "observed output, not assumed"
    )

    episode_2_plan = episode_1_plan.model_copy(
        update={"integration_topology": "platform"}
    )
    episode_2 = await execute_fortune5_mna_simulation(episode_2_plan)

    assert episode_1.episode_id != episode_2.episode_id
    assert episode_1.selected_plan != episode_2.selected_plan
    assert episode_1.verified is True
    assert episode_2.verified is True
    assert episode_1.selection_digest != episode_2.selection_digest
