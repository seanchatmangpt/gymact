"""DfCM transaction frontier and LLM-free Fortune-5-pattern M&A simulation.

The scenario is deliberately synthetic. GymAct holds and mutates only the
bounded ``mna`` gym world; there is no brokerage, filing, payment, signature,
company-control, or other external transaction port.

SELECT remains external: ``fortune5_mna_space`` preserves the reversible deal
possibility space and the caller supplies ``MnaSelectedPlan``. CONSTRUCT is
performed by logical ggen agents compiled from the M&A pack's RDF ABox. DO
mutates only the synthetic gym under explicit standard/elevated authority and
produces normal GymAct receipts.
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from gymact.combinatorial import (
    CombinationSpace,
    ExplorationBounds,
    Factor,
    manufacture_combination_space,
)
from gymact.evidence import digest
from gymact.ggen_agent import (
    GgenAgentRuntime,
    ProjectionGgenManufacturer,
    compile_ggen_agent_specs,
    load_task_agent_assignments,
    manufacture_ggen_agent_space,
)
from gymact.gyms.mna import MNA_PACK_DIR, build_mna_provider
from gymact.gyms.ontology_gym import TieredAuthorityResolver, capability_iri
from gymact.models import (
    ActuationIntent,
    FrozenModel,
    MaterializationIntent,
    Standing,
)
from gymact.runtime import GymAct

STANDARD_AUTHORITY = "urn:gymact:mna:authority:synthetic-deal-team"
BOARD_AUTHORITY = "urn:gymact:mna:authority:synthetic-board"
PRINCIPAL = "urn:gymact:mna:principal:llmless-manufactured-organization"
SCENARIO = "fortune5-synthetic-merger-acquisition"


class MnaSelectedPlan(FrozenModel):
    """One externally selected point on the reversible transaction frontier."""

    transaction_form: Literal[
        "stock_purchase",
        "statutory_merger",
        "asset_purchase",
    ]
    consideration: Literal["cash", "stock", "mixed"]
    integration_topology: Literal["absorb", "federate", "platform"]
    operating_model: Literal[
        "centralized",
        "business_unit",
        "holding_company",
    ]
    separation_strategy: Literal[
        "day_one",
        "transitional_services",
        "dual_run",
    ]
    regulatory_sequence: Literal[
        "sign_then_clear",
        "clear_then_sign",
        "staged_close",
    ]


class MnaSimulationResult(FrozenModel):
    """Evidence summary for one completed synthetic transaction episode."""

    scenario: str
    standing: Standing
    verified: bool
    episode_id: str
    transaction_frontier_cardinality: int
    transaction_frontier_truncated: bool
    agent_frontier_cardinality: int
    selected_plan: MnaSelectedPlan
    selection_digest: str
    facts: tuple[str, ...]
    receipt_ids: tuple[str, ...]
    manufactured_agent_receipts: tuple[str, ...]
    llm_calls: Literal[0] = 0
    standard_close_refusal_receipt_id: str
    simulated_close_receipt_id: str
    external_transaction_attempted: Literal[False] = False
    external_transaction_reason: str = "NO_EXTERNAL_TRANSACTION_PORT"


def fortune5_mna_space(*, max_combinations: int = 10000) -> CombinationSpace:
    """Preserve a 729-point reversible deal-design frontier without selecting."""
    return manufacture_combination_space(
        (
            Factor(
                factor_id="transaction_form",
                alternatives=(
                    "stock_purchase",
                    "statutory_merger",
                    "asset_purchase",
                ),
            ),
            Factor(
                factor_id="consideration",
                alternatives=("cash", "stock", "mixed"),
            ),
            Factor(
                factor_id="integration_topology",
                alternatives=("absorb", "federate", "platform"),
            ),
            Factor(
                factor_id="operating_model",
                alternatives=(
                    "centralized",
                    "business_unit",
                    "holding_company",
                ),
            ),
            Factor(
                factor_id="separation_strategy",
                alternatives=(
                    "day_one",
                    "transitional_services",
                    "dual_run",
                ),
            ),
            Factor(
                factor_id="regulatory_sequence",
                alternatives=(
                    "sign_then_clear",
                    "clear_then_sign",
                    "staged_close",
                ),
            ),
        ),
        bounds=ExplorationBounds(max_combinations=max_combinations),
    )


def fortune5_mna_agent_space() -> CombinationSpace:
    """Preserve 216 possible logical organizations before admitting six agents."""
    return manufacture_ggen_agent_space(
        roles=(
            "strategy",
            "diligence",
            "finance",
            "regulatory",
            "integration",
            "governance",
        ),
        planners=("workflow", "constraint", "graph-search"),
        objectives=("value", "risk", "flow-time"),
        observation_projections=("full-state", "facts-only"),
        action_projections=("capability-payload", "capability-only"),
        packs=("urn:gymact:mna:pack-mna",),
        max_combinations=1000,
    )


def _validate_selected_plan(
    space: CombinationSpace,
    plan: MnaSelectedPlan,
) -> str:
    assignments = plan.model_dump(mode="python")
    if not any(
        combination.assignments == assignments
        for combination in space.combinations
    ):
        if space.truncated:
            raise ValueError(
                "SELECTED_PLAN_NOT_MATERIALIZED_WITHIN_DFCM_BOUNDS"
            )
        raise ValueError("SELECTED_PLAN_NOT_IN_DFCM_SPACE")
    return digest(assignments)


def _task_payload(
    *,
    task_identifier: str,
    subject: str | None,
    plan: MnaSelectedPlan,
    selection_digest: str,
) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    if subject is not None:
        payload["subject"] = subject
    if task_identifier == "mna.40.transaction-structure":
        payload["selected_plan"] = plan.model_dump(mode="json")
        payload["selection_digest"] = selection_digest
    return payload


async def execute_fortune5_mna_simulation(
    plan: MnaSelectedPlan,
) -> MnaSimulationResult:
    """Execute a complete synthetic Fortune-5-pattern M&A process with zero LMs."""
    transaction_space = fortune5_mna_space()
    selection_digest = _validate_selected_plan(transaction_space, plan)
    agent_space = fortune5_mna_agent_space()

    specs = compile_ggen_agent_specs(MNA_PACK_DIR)
    if not specs:
        raise RuntimeError("MNA_GGEN_AGENT_SPECS_EMPTY")
    agents = GgenAgentRuntime(specs, ProjectionGgenManufacturer())
    assignments = load_task_agent_assignments(MNA_PACK_DIR)
    known_agents = {spec.agent_id for spec in specs}

    provider = build_mna_provider()
    expected_tasks = {task.identifier for task in provider.tasks()}
    if set(assignments) != expected_tasks:
        raise RuntimeError("MNA_TASK_AGENT_ASSIGNMENTS_INCOMPLETE")
    if not set(assignments.values()).issubset(known_agents):
        raise RuntimeError("MNA_TASK_AGENT_ASSIGNMENT_UNKNOWN_AGENT")

    resolver = TieredAuthorityResolver(
        elevated_capabilities=provider.elevated_capability_iris(),
        standard_ref=STANDARD_AUTHORITY,
        elevated_ref=BOARD_AUTHORITY,
    )
    gym = GymAct(authority_resolver=resolver)
    gym.register_provider(provider)
    materialization = await gym.materialize(
        MaterializationIntent(
            provider="mna",
            scenario=SCENARIO,
            principal=PRINCIPAL,
            idempotency_key=f"mna:{selection_digest}:materialize",
        )
    )
    if not materialization.accepted or materialization.episode is None:
        raise RuntimeError(
            materialization.receipt.reason or "MNA_MATERIALIZATION_REFUSED"
        )
    episode_id = materialization.episode.episode_id

    manufactured_receipts: list[str] = []
    standard_close_refusal_receipt_id: str | None = None
    simulated_close_receipt_id: str | None = None

    for task in provider.tasks():
        capability = capability_iri(provider_name="mna", task=task)
        agent_id = assignments[task.identifier]
        authority_ref = (
            BOARD_AUTHORITY
            if task.family in provider.elevated_task_families
            else STANDARD_AUTHORITY
        )
        subjects: tuple[str | None, ...] = (
            task.subjects if len(task.subjects) > 1 else (None,)
        )

        for subject in subjects:
            observed = await gym.observe(episode_id)
            payload = _task_payload(
                task_identifier=task.identifier,
                subject=subject,
                plan=plan,
                selection_digest=selection_digest,
            )
            manufactured = await agents.invoke(
                agent_id,
                observation=observed.state,
                inputs={"capability": capability, "payload": payload},
            )
            if manufactured.standing is not Standing.ALIVE:
                raise RuntimeError(manufactured.reason)
            manufactured_receipts.append(manufactured.receipt_digest)

            output_capability = manufactured.output["capability"]
            output_payload = manufactured.output["payload"]

            if (
                task.family == "simulated-close"
                and standard_close_refusal_receipt_id is None
            ):
                refused = await gym.act(
                    ActuationIntent(
                        episode_id=episode_id,
                        capability=output_capability,
                        payload=output_payload,
                        authority_ref=STANDARD_AUTHORITY,
                        principal=PRINCIPAL,
                        idempotency_key=(
                            f"mna:{selection_digest}:close-standard-refusal"
                        ),
                    )
                )
                if refused.accepted or refused.standing is not Standing.REFUSED:
                    raise RuntimeError(
                        "MNA_CLOSE_MUST_REFUSE_STANDARD_AUTHORITY"
                    )
                standard_close_refusal_receipt_id = refused.receipt.receipt_id

            result = await gym.act(
                ActuationIntent(
                    episode_id=episode_id,
                    capability=output_capability,
                    payload=output_payload,
                    authority_ref=authority_ref,
                    principal=PRINCIPAL,
                    idempotency_key=digest(
                        {
                            "selection": selection_digest,
                            "task": task.identifier,
                            "subject": subject,
                        }
                    ),
                )
            )
            if not result.accepted:
                raise RuntimeError(
                    f"{task.identifier}:{result.receipt.reason}"
                )
            if task.family == "simulated-close":
                simulated_close_receipt_id = result.receipt.receipt_id

    verification = await gym.verify(episode_id, {"goal_reached": True})
    observed = await gym.observe(episode_id)
    receipts = tuple(
        receipt.receipt_id for receipt in gym.episode_receipts(episode_id)
    )

    if (
        standard_close_refusal_receipt_id is None
        or simulated_close_receipt_id is None
    ):
        raise RuntimeError("MNA_CLOSE_EVIDENCE_INCOMPLETE")
    if not verification.passed:
        raise RuntimeError("MNA_FINAL_VERIFICATION_FAILED")

    await gym.teardown(episode_id, authority_ref=BOARD_AUTHORITY)

    return MnaSimulationResult(
        scenario=SCENARIO,
        standing=Standing.ALIVE,
        verified=True,
        episode_id=episode_id,
        transaction_frontier_cardinality=transaction_space.total_cardinality,
        transaction_frontier_truncated=transaction_space.truncated,
        agent_frontier_cardinality=agent_space.total_cardinality,
        selected_plan=plan,
        selection_digest=selection_digest,
        facts=tuple(observed.state["facts"]),
        receipt_ids=receipts,
        manufactured_agent_receipts=tuple(manufactured_receipts),
        standard_close_refusal_receipt_id=standard_close_refusal_receipt_id,
        simulated_close_receipt_id=simulated_close_receipt_id,
    )
