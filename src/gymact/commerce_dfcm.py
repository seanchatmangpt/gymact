"""Post-AGI DfCM orchestration for provider-neutral Fortune-5 commerce.

This module composes GymAct's existing combinatorial maximum and deterministic
ggen-agent primitives with the ``commerce-dfcm`` environment. The complete
commercial design space remains powerless until a caller supplies one explicit
selection. Deterministic agents then manufacture every bounded internal action.
The seven marketplace/legal DO edges are never exposed to the executable provider
and therefore remain an explicit irreversible frontier for later adapter packs.

No LLM, marketplace SDK, cloud credential, payment credential, seller account, or
external authority is used here.
"""

from __future__ import annotations

from typing import Any, Literal

from gymact.authority import AllowListAuthorityResolver
from gymact.combinatorial import (
    CombinationSpace,
    ExplorationBounds,
    Factor,
    manufacture_combination_space,
)
from gymact.evidence import digest
from gymact.ggen_agent import (
    CallableGgenManufacturer,
    GgenAgentRuntime,
    GgenAgentSpec,
    manufacture_ggen_agent_space,
)
from gymact.gyms.commerce_dfcm_gym import (
    COMMERCE_DFCM_CAPABILITIES,
    COMMERCE_DFCM_EXTERNAL_FRONTIER,
    COMMERCE_DFCM_SEMANTIC_CAPABILITIES,
    CommerceDfcmProvider,
)
from gymact.kernel import GymAct
from gymact.models import ActuationIntent, Consequence, FrozenModel, Standing

INTERNAL_AUTHORITY = "urn:gymact:commerce-dfcm:authority:bounded-internal"
PRINCIPAL = "urn:gymact:commerce-dfcm:principal:deterministic-manufacturer"
SCENARIO = "fortune-5-commerce"
PACK_REF = "urn:ggen:pack:post-agi-commerce-core"


class CommerceSelectedPlan(FrozenModel):
    """One explicitly selected point in the reversible commercial design space."""

    billing_authority: Literal["DIRECT", "EXTERNAL_COMMERCE"]
    pricing_model: Literal["usage", "seat", "subscription", "hybrid"]
    entitlement_cardinality: Literal["single", "concurrent"]
    identity_binding: Literal["tenant", "account", "legal-entity"]
    usage_projection: Literal["event", "aggregate", "hybrid"]
    packaging_topology: Literal["helm-first", "kubernetes-first", "oci-first"]
    supply_chain_policy: Literal["standard", "strict"]
    support_tier: Literal["standard", "premium", "enterprise-247"]


class CommerceDfcmExecution(FrozenModel):
    """Evidence summary for one complete marketplace-free DfCM episode."""

    standing: Standing
    internal_standing: Standing
    external_standing: Standing
    verified: bool
    episode_id: str
    design_frontier_cardinality: int
    design_frontier_truncated: bool
    agent_frontier_cardinality: int
    semantic_capability_count: int
    executable_capability_count: int
    external_frontier_count: int
    selected_plan: CommerceSelectedPlan
    selection_digest: str
    executed_alive_bindings: tuple[str, ...]
    exercised_refusal_bindings: tuple[str, ...]
    external_frontier_bindings: tuple[str, ...]
    manufactured_agent_receipts: tuple[str, ...]
    runtime_receipt_ids: tuple[str, ...]
    llm_calls: Literal[0] = 0
    marketplace_attempted: Literal[False] = False
    external_reason: str = "MARKETPLACE_AND_LEGAL_DO_OUTSIDE_GYM_AUTHORITY"


class _ManufacturedAction(FrozenModel):
    binding: str
    capability: str
    payload: dict[str, Any]
    agent_id: str
    manufacture_receipt: str


def commerce_design_space(*, max_combinations: int = 10000) -> CombinationSpace:
    """Preserve the full 2,592-point reversible commercial design frontier."""
    return manufacture_combination_space(
        (
            Factor(
                factor_id="billing_authority",
                alternatives=("DIRECT", "EXTERNAL_COMMERCE"),
            ),
            Factor(
                factor_id="pricing_model",
                alternatives=("usage", "seat", "subscription", "hybrid"),
            ),
            Factor(
                factor_id="entitlement_cardinality",
                alternatives=("single", "concurrent"),
            ),
            Factor(
                factor_id="identity_binding",
                alternatives=("tenant", "account", "legal-entity"),
            ),
            Factor(
                factor_id="usage_projection",
                alternatives=("event", "aggregate", "hybrid"),
            ),
            Factor(
                factor_id="packaging_topology",
                alternatives=("helm-first", "kubernetes-first", "oci-first"),
            ),
            Factor(
                factor_id="supply_chain_policy",
                alternatives=("standard", "strict"),
            ),
            Factor(
                factor_id="support_tier",
                alternatives=("standard", "premium", "enterprise-247"),
            ),
        ),
        bounds=ExplorationBounds(max_combinations=max_combinations),
    )


def commerce_agent_space() -> CombinationSpace:
    """Preserve the logical organization frontier independently of active WIP."""
    return manufacture_ggen_agent_space(
        roles=("commercial", "identity", "entitlement", "metering", "supply-chain", "governance"),
        planners=("workflow", "constraint", "graph-search"),
        objectives=("flow-time", "risk", "evidence"),
        observation_projections=("full-state", "identity-and-receipts"),
        action_projections=("capability-payload", "capability-only"),
        packs=(PACK_REF,),
        max_combinations=1000,
    )


def _validate_selection(space: CombinationSpace, plan: CommerceSelectedPlan) -> str:
    assignments = plan.model_dump(mode="python")
    if not any(item.assignments == assignments for item in space.combinations):
        if space.truncated:
            raise ValueError("SELECTED_COMMERCE_PLAN_NOT_MATERIALIZED_WITHIN_DFCM_BOUNDS")
        raise ValueError("SELECTED_COMMERCE_PLAN_NOT_IN_DFCM_SPACE")
    return digest(assignments)


def _agent_specs() -> tuple[GgenAgentSpec, ...]:
    return tuple(
        GgenAgentSpec(
            agent_id=f"commerce-{role}",
            role_ref=f"urn:gymact:commerce-dfcm:role:{role}",
            planner_ref="urn:gymact:planner:deterministic-workflow",
            objective_ref="urn:gymact:objective:maximize-evidence-per-unit-time",
            observation_projection_ref="urn:gymact:projection:commerce-state",
            action_projection_ref="urn:gymact:projection:capability-payload",
            pack_ref=PACK_REF,
            observation_keys=(),
            output_keys=("capability", "payload"),
            max_wip=1,
            mcp_tool_name=f"commerce_{role}",
        )
        for role in (
            "commercial",
            "identity",
            "entitlement",
            "metering",
            "supply-chain",
            "governance",
        )
    )


def _manufacture_action(
    *, spec: GgenAgentSpec, observation: dict[str, Any], inputs: dict[str, Any]
) -> dict[str, Any]:
    del spec, observation
    capability = inputs.get("capability")
    payload = inputs.get("payload")
    if not isinstance(capability, str) or not capability:
        raise ValueError("COMMERCE_CAPABILITY_REQUIRED")
    if not isinstance(payload, dict):
        raise TypeError("COMMERCE_PAYLOAD_MUST_BE_OBJECT")
    return {"capability": capability, "payload": payload}


def _agent_for(binding: str) -> str:
    if binding.startswith(("agreement.", "billing-authority", "credit.", "refund.")):
        return "commerce-commercial"
    if binding.startswith("identity."):
        return "commerce-identity"
    if binding.startswith(("entitlement.", "support.")):
        return "commerce-entitlement"
    if binding.startswith(("usage.", "pricing.", "meter.", "provider.", "settlement.")):
        return "commerce-metering"
    if binding.startswith(("packaging.", "supply-chain.", "artifact.")):
        return "commerce-supply-chain"
    return "commerce-governance"


def _pricing(plan: CommerceSelectedPlan) -> tuple[list[dict[str, Any]], str]:
    if plan.pricing_model == "usage":
        return ([{"dimension_id": "calls", "unit": "call", "unit_price_micros": 7}], "calls")
    if plan.pricing_model == "seat":
        return ([{"dimension_id": "seats", "unit": "seat", "unit_price_micros": 1000}], "seats")
    if plan.pricing_model == "subscription":
        return (
            [{"dimension_id": "subscription_units", "unit": "unit", "unit_price_micros": 5000}],
            "subscription_units",
        )
    return (
        [
            {"dimension_id": "calls", "unit": "call", "unit_price_micros": 5},
            {"dimension_id": "seats", "unit": "seat", "unit_price_micros": 1000},
        ],
        "calls",
    )


def _grant(subject: str, operation: str) -> dict[str, str]:
    return {
        "grant_id": digest({"subject": subject, "operation": operation, "authority": INTERNAL_AUTHORITY}),
        "authority": INTERNAL_AUTHORITY,
        "subject_id": subject,
        "allowed_operation": operation,
        "evidence_ref": "urn:gymact:commerce-dfcm:evidence:bounded-internal-authority",
    }


def _capability(runtime: GymAct, episode_id: str, binding: str):
    matches = tuple(
        item for item in runtime.capabilities(episode_id) if item.binding == binding
    )
    if len(matches) != 1:
        raise RuntimeError(f"COMMERCE_CAPABILITY_NOT_UNAMBIGUOUS:{binding}:{len(matches)}")
    return matches[0]


async def _manufacture(
    *,
    agents: GgenAgentRuntime,
    runtime: GymAct,
    episode_id: str,
    binding: str,
    payload: dict[str, Any],
) -> _ManufacturedAction:
    capability = _capability(runtime, episode_id, binding)
    observed = await runtime.observe(episode_id)
    agent_id = _agent_for(binding)
    result = await agents.invoke(
        agent_id,
        observation=observed.state,
        inputs={"capability": capability.iri, "payload": payload},
    )
    if result.standing is not Standing.ALIVE:
        raise RuntimeError(result.reason)
    return _ManufacturedAction(
        binding=binding,
        capability=str(result.output["capability"]),
        payload=dict(result.output["payload"]),
        agent_id=agent_id,
        manufacture_receipt=result.receipt_digest,
    )


async def _execute_alive(
    *,
    agents: GgenAgentRuntime,
    runtime: GymAct,
    episode_id: str,
    binding: str,
    payload: dict[str, Any],
    ordinal: int,
) -> tuple[str, str, str | None]:
    manufactured = await _manufacture(
        agents=agents,
        runtime=runtime,
        episode_id=episode_id,
        binding=binding,
        payload=payload,
    )
    capability = _capability(runtime, episode_id, binding)
    if capability.consequence is Consequence.READ:
        effect = await runtime.read(episode_id, manufactured.capability, manufactured.payload)
        if effect.get("standing") != "ALIVE":
            raise RuntimeError(f"COMMERCE_INNER_NOT_ALIVE:{binding}:{effect}")
        return binding, manufactured.manufacture_receipt, None

    result = await runtime.act(
        ActuationIntent(
            episode_id=episode_id,
            capability=manufactured.capability,
            payload=manufactured.payload,
            authority_ref=INTERNAL_AUTHORITY,
            principal=PRINCIPAL,
            idempotency_key=digest(
                {"episode": episode_id, "binding": binding, "ordinal": ordinal, "payload": payload}
            ),
        )
    )
    if not result.accepted:
        raise RuntimeError(f"COMMERCE_OUTER_REFUSED:{binding}:{result.receipt.reason}")
    if result.effect is None or result.effect.get("standing") != "ALIVE":
        raise RuntimeError(f"COMMERCE_INNER_NOT_ALIVE:{binding}:{result.effect}")
    return binding, manufactured.manufacture_receipt, result.receipt.receipt_id


async def _execute_expected_refusal(
    *,
    agents: GgenAgentRuntime,
    runtime: GymAct,
    episode_id: str,
    binding: str,
    payload: dict[str, Any],
    expected_code: str,
    ordinal: int,
) -> tuple[str, str, str]:
    manufactured = await _manufacture(
        agents=agents,
        runtime=runtime,
        episode_id=episode_id,
        binding=binding,
        payload=payload,
    )
    result = await runtime.act(
        ActuationIntent(
            episode_id=episode_id,
            capability=manufactured.capability,
            payload=manufactured.payload,
            authority_ref=INTERNAL_AUTHORITY,
            principal=PRINCIPAL,
            idempotency_key=digest(
                {
                    "episode": episode_id,
                    "binding": binding,
                    "ordinal": ordinal,
                    "expected_refusal": expected_code,
                }
            ),
        )
    )
    if not result.accepted or result.effect is None:
        raise RuntimeError(f"COMMERCE_REFUSAL_COURT_DID_NOT_EXECUTE:{binding}")
    if result.effect.get("standing") != "REFUSED":
        raise RuntimeError(f"COMMERCE_EXPECTED_REFUSAL_MISSING:{binding}:{result.effect}")
    refusal = result.effect.get("refusal")
    if not isinstance(refusal, dict) or refusal.get("code") != expected_code:
        raise RuntimeError(f"COMMERCE_WRONG_REFUSAL:{binding}:{refusal}")
    return binding, manufactured.manufacture_receipt, result.receipt.receipt_id


async def execute_commerce_dfcm(plan: CommerceSelectedPlan) -> CommerceDfcmExecution:
    """Execute every marketplace-free commerce capability and stop at external DO.

    Three internal admission capabilities are intentionally exercised as negative
    courts: deterministic replay, provider acceptance from fixture evidence, and
    settlement without admitted provider acceptance. Their typed refusals are the
    successful result. The other 22 internal capabilities must produce ALIVE inner
    evidence. The seven external DO capabilities are never passed to ``GymAct.act``.
    """
    design_space = commerce_design_space()
    selection_digest = _validate_selection(design_space, plan)
    agent_space = commerce_agent_space()
    specs = _agent_specs()
    manufacturer = CallableGgenManufacturer({spec.agent_id: _manufacture_action for spec in specs})
    agents = GgenAgentRuntime(specs, manufacturer)

    runtime = GymAct(authority_resolver=AllowListAuthorityResolver({INTERNAL_AUTHORITY}))
    runtime.register_provider(CommerceDfcmProvider())
    materialized = await runtime.create_episode(
        "commerce-dfcm",
        scenario=SCENARIO,
        config={"requires_authority": True},
        idempotency_key=f"commerce:{selection_digest}:materialize",
    )
    if not materialized.accepted or materialized.episode is None:
        raise RuntimeError(materialized.receipt.reason or "COMMERCE_MATERIALIZATION_REFUSED")
    episode_id = materialized.episode.episode_id

    price, usage_dimension = _pricing(plan)
    agreement_id = f"agreement-{selection_digest[:12]}"
    entitlement_id = f"entitlement-{selection_digest[:12]}"
    account_id = "account-fortune5"
    tenant_id = "tenant-fortune5"
    product_id = "chatman-ecosystem"
    base_agreement = {
        "agreement_id": agreement_id,
        "legal_entity_id": "legal-entity-fortune5",
        "account_id": account_id,
        "product_id": product_id,
        "offer_id": "offer-selected",
        "billing_authority": plan.billing_authority,
        "pricing": price,
        "effective_at": "2026-08-19T00:00:00Z",
        "expires_at": "2027-08-19T00:00:00Z",
        "negotiated_terms_ref": f"urn:gymact:commerce-dfcm:selection:{selection_digest}",
    }
    packaging = {
        "helm_chart": True,
        "stable_kubernetes_apis": True,
        "sbom": True,
        "vulnerability_scan": True,
        "signed_provenance": True,
        "portable_registry_artifact": True,
    }

    alive: list[str] = []
    refusal: list[str] = []
    manufactured_receipts: list[str] = []
    runtime_receipts: list[str] = []
    ordinal = 0

    async def alive_step(binding: str, payload: dict[str, Any]) -> None:
        nonlocal ordinal
        ordinal += 1
        item, manufactured_receipt, runtime_receipt = await _execute_alive(
            agents=agents,
            runtime=runtime,
            episode_id=episode_id,
            binding=binding,
            payload=payload,
            ordinal=ordinal,
        )
        alive.append(item)
        manufactured_receipts.append(manufactured_receipt)
        if runtime_receipt is not None:
            runtime_receipts.append(runtime_receipt)

    async def refusal_step(binding: str, payload: dict[str, Any], code: str) -> None:
        nonlocal ordinal
        ordinal += 1
        item, manufactured_receipt, runtime_receipt = await _execute_expected_refusal(
            agents=agents,
            runtime=runtime,
            episode_id=episode_id,
            binding=binding,
            payload=payload,
            expected_code=code,
            ordinal=ordinal,
        )
        refusal.append(item)
        manufactured_receipts.append(manufactured_receipt)
        runtime_receipts.append(runtime_receipt)

    await alive_step("agreement.admit", {"agreement": base_agreement})
    await alive_step("billing-authority.fence", {"agreement": base_agreement})
    identity_subject = {
        "tenant": tenant_id,
        "account": account_id,
        "legal-entity": "legal-entity-fortune5",
    }[plan.identity_binding]
    await alive_step(
        "identity.bind",
        {
            "binding_id": "identity-primary",
            "account_id": account_id,
            "tenant_id": tenant_id,
            "issuer": "urn:gymact:commerce-dfcm:identity:selected",
            "subject": identity_subject,
        },
    )

    create_event = {
        "event_id": "entitlement-create-primary",
        "source": "admitted-external-event",
        "kind": "CREATE",
        "agreement_id": agreement_id,
        "entitlement_id": entitlement_id,
        "tenant_id": tenant_id,
        "product_id": product_id,
        "revision": 1,
        "quantity": 1,
        "capabilities": ["api", "support"],
        "support_tier": plan.support_tier,
    }
    activate_event = {**create_event, "event_id": "entitlement-activate-primary", "kind": "ACTIVATE", "revision": 2}
    await alive_step(
        "entitlement.apply-event",
        {"event": create_event, "grant": _grant(entitlement_id, "entitlement.apply-event")},
    )
    await alive_step(
        "entitlement.lifecycle",
        {"event": activate_event, "grant": _grant(entitlement_id, "entitlement.apply-event")},
    )

    if plan.entitlement_cardinality == "concurrent":
        second_agreement = {**base_agreement, "agreement_id": f"{agreement_id}-2", "offer_id": "offer-concurrent"}
        second_entitlement = f"{entitlement_id}-2"
        await alive_step("agreement.admit", {"agreement": second_agreement})
        second_create = {
            **create_event,
            "event_id": "entitlement-create-secondary",
            "agreement_id": second_agreement["agreement_id"],
            "entitlement_id": second_entitlement,
            "tenant_id": "tenant-fortune5-secondary",
        }
        second_activate = {
            **second_create,
            "event_id": "entitlement-activate-secondary",
            "kind": "ACTIVATE",
            "revision": 2,
        }
        await alive_step(
            "entitlement.apply-event",
            {"event": second_create, "grant": _grant(second_entitlement, "entitlement.apply-event")},
        )
        await alive_step(
            "entitlement.lifecycle",
            {"event": second_activate, "grant": _grant(second_entitlement, "entitlement.apply-event")},
        )

    await alive_step("entitlement.concurrent", {})
    await refusal_step(
        "replay.idempotent",
        {"event": activate_event, "grant": _grant(entitlement_id, "entitlement.apply-event")},
        "REFUSED:DUPLICATE_OR_STALE_EVENT",
    )

    observation = {
        "observation_id": "usage-primary",
        "entitlement_id": entitlement_id,
        "tenant_id": tenant_id,
        "dimension_id": usage_dimension,
        "quantity": 3,
        "observed_at": "2026-08-19T00:01:00Z",
        "projection": plan.usage_projection,
    }
    await alive_step("usage.observe", {"observation": observation})
    await alive_step("pricing.validate", {"observation_id": "usage-primary"})
    await alive_step("usage.admit", {"observation_id": "usage-primary"})
    await alive_step(
        "meter.construct",
        {"intent_id": "meter-primary", "observation_ids": ["usage-primary"]},
    )
    await refusal_step(
        "provider.acceptance.admit",
        {
            "acceptance_id": "fixture-acceptance",
            "intent_id": "meter-primary",
            "provider": "fixture",
            "observed": True,
            "evidence_ref": "urn:gymact:fixture:not-live",
            "accepted_quantity": 3,
            "evidence_origin": "FIXTURE",
        },
        "REFUSED:PROVIDER_ACCEPTANCE_NOT_OBSERVED",
    )
    await refusal_step(
        "settlement.reconcile",
        {"settlement_id": "settlement-without-provider", "acceptance_id": "fixture-acceptance"},
        "REFUSED:SETTLEMENT_WITHOUT_PROVIDER_ACCEPTANCE",
    )

    await alive_step("support.entitle", {"entitlement_id": entitlement_id})
    for binding in (
        "packaging.helm",
        "packaging.k8s-stable-api",
        "supply-chain.sbom",
        "supply-chain.vulnerability-scan",
        "supply-chain.provenance",
        "artifact.portable-registry",
    ):
        await alive_step(binding, {"packaging": packaging, "topology": plan.packaging_topology})

    await alive_step(
        "credit.construct",
        {"adjustment_id": "credit-sla", "agreement_id": agreement_id, "amount_micros": 1, "reason": "simulation-sla"},
    )
    await alive_step(
        "refund.construct",
        {"adjustment_id": "refund-correction", "agreement_id": agreement_id, "amount_micros": 1, "reason": "simulation-correction"},
    )
    await alive_step(
        "agreement.amend",
        {
            "agreement_id": agreement_id,
            "pricing": price,
            "offer_id": "offer-selected-amended",
            "grant": _grant(agreement_id, "agreement.amend"),
        },
    )
    await alive_step(
        "agreement.renew",
        {
            "agreement_id": agreement_id,
            "expires_at": "2028-08-19T00:00:00Z",
            "grant": _grant(agreement_id, "agreement.renew"),
        },
    )
    cancel_event = {
        **activate_event,
        "event_id": "entitlement-cancel-primary",
        "kind": "CANCEL",
        "revision": 3,
    }
    await alive_step(
        "entitlement.lifecycle",
        {"event": cancel_event, "grant": _grant(entitlement_id, "entitlement.apply-event")},
    )
    await alive_step(
        "agreement.cancel",
        {"agreement_id": agreement_id, "grant": _grant(agreement_id, "agreement.cancel")},
    )

    semantic_ids = {item.binding for item in COMMERCE_DFCM_SEMANTIC_CAPABILITIES}
    exercised = set(alive) | set(refusal)
    external = tuple(sorted(item.binding for item in COMMERCE_DFCM_EXTERNAL_FRONTIER))
    if exercised | set(external) != semantic_ids:
        missing = sorted(semantic_ids - exercised - set(external))
        raise RuntimeError(f"COMMERCE_CAPABILITY_CLOSURE_NOT_EXERCISED:{missing}")
    if exercised & set(external):
        raise RuntimeError("EXTERNAL_COMMERCE_DO_ENTERED_EXECUTABLE_EPISODE")

    verification = await runtime.verify(
        episode_id,
        {
            "packaging_admitted": True,
            "semantic_capability_count": 32,
            "executable_capability_count": 25,
            "external_frontier_count": 7,
        },
    )
    if not verification.passed:
        raise RuntimeError("COMMERCE_FINAL_VERIFICATION_FAILED")

    all_runtime_receipts = tuple(
        receipt.receipt_id for receipt in runtime.episode_receipts(episode_id)
    )
    await runtime.teardown(episode_id, authority_ref=INTERNAL_AUTHORITY)

    return CommerceDfcmExecution(
        standing=Standing.ALIVE,
        internal_standing=Standing.ALIVE,
        external_standing=Standing.BLOCKED,
        verified=True,
        episode_id=episode_id,
        design_frontier_cardinality=design_space.total_cardinality,
        design_frontier_truncated=design_space.truncated,
        agent_frontier_cardinality=agent_space.total_cardinality,
        semantic_capability_count=len(COMMERCE_DFCM_SEMANTIC_CAPABILITIES),
        executable_capability_count=len(COMMERCE_DFCM_CAPABILITIES),
        external_frontier_count=len(COMMERCE_DFCM_EXTERNAL_FRONTIER),
        selected_plan=plan,
        selection_digest=selection_digest,
        executed_alive_bindings=tuple(sorted(set(alive))),
        exercised_refusal_bindings=tuple(sorted(set(refusal))),
        external_frontier_bindings=external,
        manufactured_agent_receipts=tuple(manufactured_receipts),
        runtime_receipt_ids=all_runtime_receipts,
    )
