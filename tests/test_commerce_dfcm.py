from gymact.gyms.commerce_dfcm import (
    BillingAuthority,
    BrokerGrant,
    CAPABILITIES,
    CommerceWorld,
    CommercialAgreement,
    EntitlementEvent,
    EntitlementState,
    EventKind,
    ExternalAcceptance,
    ExternalBlocker,
    PackagingEvidence,
    PricingDimension,
    Refusal,
    RefusalCode,
    Standing,
    UsageObservation,
    capability_digest,
)


def agreement(aid="a-1", authority=BillingAuthority.EXTERNAL_COMMERCE):
    return CommercialAgreement(
        agreement_id=aid,
        legal_entity_id="legal-1",
        account_id="acct-1",
        product_id="chatman",
        offer_id="offer-enterprise",
        billing_authority=authority,
        pricing=(PricingDimension("api_calls", "call", 5),),
        effective_at="2026-08-19T00:00:00Z",
    )


def grant(subject, operation="entitlement.apply-event"):
    return BrokerGrant("grant-1", "brce-test", subject, operation, "test:authority")


def event(eid, kind, rev, entitlement="ent-1", agreement_id="a-1", tenant="tenant-1"):
    return EntitlementEvent(
        event_id=eid,
        source="external",
        kind=kind,
        agreement_id=agreement_id,
        entitlement_id=entitlement,
        tenant_id=tenant,
        product_id="chatman",
        revision=rev,
        quantity=10,
        capabilities=frozenset({"api", "mcp", "a2a"}),
        support_tier="enterprise-247",
    )


def activate(world, entitlement="ent-1", agreement_id="a-1", tenant="tenant-1"):
    created, receipt = world.apply_entitlement_event(
        "external",
        event("e-create-"+entitlement, EventKind.CREATE, 1, entitlement, agreement_id, tenant),
        grant=grant(entitlement),
    )
    assert created and not isinstance(receipt, Refusal)
    active, receipt = world.apply_entitlement_event(
        "external",
        event("e-active-"+entitlement, EventKind.ACTIVATE, 2, entitlement, agreement_id, tenant),
        grant=grant(entitlement),
    )
    assert active and active.state is EntitlementState.ACTIVE
    assert not isinstance(receipt, Refusal)
    return active


def test_capability_class_closure_is_large_and_stable():
    assert len(CAPABILITIES) >= 30
    assert len({c.capability_id for c in CAPABILITIES}) == len(CAPABILITIES)
    assert len(capability_digest()) == 64


def test_billing_authority_is_exactly_one_per_agreement_identity():
    world = CommerceWorld()
    admitted, _ = world.admit_agreement(agreement(authority=BillingAuthority.DIRECT))
    assert admitted
    rejected, refusal = world.admit_agreement(
        agreement(authority=BillingAuthority.EXTERNAL_COMMERCE)
    )
    assert rejected is None
    assert refusal.code is RefusalCode.MULTIPLE_BILLING_AUTHORITIES


def test_entitlement_do_requires_brce_and_replay_is_refused():
    world = CommerceWorld()
    world.admit_agreement(agreement())
    candidate, refusal = world.apply_entitlement_event(
        "external", event("e-1", EventKind.CREATE, 1), grant=None
    )
    assert candidate is None
    assert refusal.code is RefusalCode.BRCE_REQUIRED

    candidate, receipt = world.apply_entitlement_event(
        "external", event("e-1", EventKind.CREATE, 1), grant=grant("ent-1")
    )
    assert candidate and receipt.receipt_id

    duplicate, refusal = world.apply_entitlement_event(
        "external", event("e-1", EventKind.CREATE, 1), grant=grant("ent-1")
    )
    assert duplicate is None
    assert refusal.code is RefusalCode.DUPLICATE_OR_STALE_EVENT


def test_concurrent_agreements_and_entitlements_do_not_collapse_identity():
    world = CommerceWorld()
    world.admit_agreement(agreement("a-1"))
    world.admit_agreement(agreement("a-2"))
    one = activate(world, "ent-1", "a-1", "tenant-1")
    two = activate(world, "ent-2", "a-2", "tenant-1")
    assert one.agreement_id != two.agreement_id
    assert one.product_id == two.product_id
    assert world.assert_identity_preservation() is None


def test_full_internal_usage_to_settlement_path_requires_real_external_acceptance():
    world = CommerceWorld()
    world.admit_agreement(agreement())
    activate(world)

    world.observe_usage(
        UsageObservation("u-1", "ent-1", "tenant-1", "api_calls", 20, "2026-08-19T01:00:00Z")
    )
    admitted, _ = world.admit_usage("u-1")
    assert admitted and admitted.admitted

    intent, _ = world.construct_meter_intent(intent_id="m-1", observation_ids=["u-1"])
    assert intent and intent.quantity == 20 and intent.amount_micros == 100

    settlement, refusal = world.reconcile(settlement_id="s-1", acceptance_id="missing")
    assert settlement is None
    assert refusal.code is RefusalCode.SETTLEMENT_WITHOUT_PROVIDER_ACCEPTANCE

    fake, refusal = world.admit_external_acceptance(
        ExternalAcceptance("acc-fake", "m-1", "provider", False, "", 20)
    )
    assert fake is None
    assert refusal.code is RefusalCode.PROVIDER_ACCEPTANCE_NOT_OBSERVED

    accepted, receipt = world.admit_external_acceptance(
        ExternalAcceptance("acc-1", "m-1", "provider", True, "provider:receipt:123", 20)
    )
    assert accepted and receipt.receipt_id
    settlement, receipt = world.reconcile(settlement_id="s-1", acceptance_id="acc-1")
    assert settlement and settlement.amount_micros == 100 and receipt.receipt_id


def test_suspension_fences_future_usage_and_cancel_is_terminal():
    world = CommerceWorld()
    world.admit_agreement(agreement())
    activate(world)
    suspended, _ = world.apply_entitlement_event(
        "external", event("e-suspend", EventKind.SUSPEND, 3), grant=grant("ent-1")
    )
    assert suspended and suspended.state is EntitlementState.SUSPENDED

    world.observe_usage(
        UsageObservation("u-2", "ent-1", "tenant-1", "api_calls", 1, "2026-08-19T02:00:00Z")
    )
    admitted, refusal = world.admit_usage("u-2")
    assert admitted is None
    assert refusal.code is RefusalCode.USAGE_WITHOUT_ACTIVE_ENTITLEMENT

    cancelled, _ = world.apply_entitlement_event(
        "external", event("e-cancel", EventKind.CANCEL, 4), grant=grant("ent-1")
    )
    assert cancelled and cancelled.state is EntitlementState.CANCELLED
    impossible, refusal = world.apply_entitlement_event(
        "external", event("e-reinstate", EventKind.REINSTATE, 5), grant=grant("ent-1")
    )
    assert impossible is None
    assert refusal.code is RefusalCode.ILLEGAL_LIFECYCLE_TRANSITION


def test_pricing_and_tenant_boundaries_fail_closed():
    world = CommerceWorld()
    world.admit_agreement(agreement())
    activate(world)
    world.observe_usage(
        UsageObservation("u-3", "ent-1", "other-tenant", "api_calls", 2, "2026-08-19T02:00:00Z")
    )
    _, refusal = world.admit_usage("u-3")
    assert refusal.code is RefusalCode.CROSS_TENANT_ENTITLEMENT

    world.observe_usage(
        UsageObservation("u-4", "ent-1", "tenant-1", "unpriced", 2, "2026-08-19T02:00:00Z")
    )
    _, refusal = world.admit_usage("u-4")
    assert refusal.code is RefusalCode.PRICING_DIMENSION_MISMATCH


def test_readiness_separates_internal_execution_from_external_authority():
    world = CommerceWorld()
    world.admit_agreement(agreement())
    activate(world)
    world.observe_usage(
        UsageObservation("u-5", "ent-1", "tenant-1", "api_calls", 3, "2026-08-19T02:00:00Z")
    )
    world.admit_usage("u-5")
    world.construct_meter_intent(intent_id="m-5", observation_ids=["u-5"])

    packaging = PackagingEvidence(True, True, True, True, True, True)
    report = world.readiness(packaging)
    assert report.internal_standing is Standing.ALIVE
    assert report.external_standing is Standing.BLOCKED
    assert report.external_blockers

    for blocker in ExternalBlocker:
        receipt = world.admit_external_blocker_evidence(blocker, f"external:{blocker}")
        assert receipt.receipt_id

    report = world.readiness(packaging)
    assert report.internal_standing is Standing.ALIVE
    assert report.external_standing is Standing.ALIVE
    assert report.marketplace_ready


def test_packaging_is_not_crowned_when_portability_or_supply_chain_evidence_is_missing():
    world = CommerceWorld()
    report = world.readiness(PackagingEvidence())
    assert report.internal_standing is Standing.PARTIAL_ALIVE
    assert "helm_chart" in report.missing_packaging
    assert "stable_kubernetes_apis" in report.missing_packaging
