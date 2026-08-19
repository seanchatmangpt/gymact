from gymact.gyms.commerce_dfcm import (
    BillingAuthority,
    BrokerGrant,
    CommercialAgreement,
    EntitlementEvent,
    EventKind,
    PackagingEvidence,
    PricingDimension,
)
from gymact.gyms.commerce_dfcm_enterprise import (
    EnterpriseCommerceWorld,
    missing_internal_handlers,
)


def agreement():
    return CommercialAgreement(
        "a",
        "legal",
        "acct",
        "product",
        "offer",
        BillingAuthority.EXTERNAL_COMMERCE,
        (PricingDimension("calls", "call", 2),),
        "2026-08-19T00:00:00Z",
    )


def grant(subject, operation):
    return BrokerGrant("g", "brce", subject, operation, "authority:test")


def test_every_internal_capability_has_an_executable_handler():
    assert missing_internal_handlers() == ()


def test_identity_agreement_adjustments_support_and_packaging_execute():
    world = EnterpriseCommerceWorld()
    world.admit_agreement(agreement())

    binding, receipt = world.bind_identity(
        binding_id="id-1",
        account_id="acct",
        tenant_id="tenant",
        issuer="https://idp.example",
        subject="subject-1",
    )
    assert binding and receipt.receipt_id

    amended, receipt = world.amend_agreement(
        "a",
        pricing=(PricingDimension("calls", "call", 3),),
        offer_id="offer-2",
        grant=grant("a", "agreement.amend"),
    )
    assert amended and amended.offer_id == "offer-2" and receipt.receipt_id

    renewed, receipt = world.renew_agreement(
        "a",
        expires_at="2027-08-19T00:00:00Z",
        grant=grant("a", "agreement.renew"),
    )
    assert renewed and renewed.expires_at and receipt.receipt_id

    credit, receipt = world.construct_credit(
        adjustment_id="c", agreement_id="a", amount_micros=100, reason="sla"
    )
    refund, _ = world.construct_refund(
        adjustment_id="r", agreement_id="a", amount_micros=50, reason="correction"
    )
    assert credit and refund and receipt.receipt_id

    create = EntitlementEvent(
        "e1",
        "external",
        EventKind.CREATE,
        "a",
        "ent",
        "tenant",
        "product",
        1,
        support_tier="enterprise-247",
        capabilities=frozenset({"api"}),
    )
    active = EntitlementEvent(
        "e2",
        "external",
        EventKind.ACTIVATE,
        "a",
        "ent",
        "tenant",
        "product",
        2,
        support_tier="enterprise-247",
        capabilities=frozenset({"api"}),
    )
    world.apply_entitlement_event(
        "external", create, grant=grant("ent", "entitlement.apply-event")
    )
    world.apply_entitlement_event(
        "external", active, grant=grant("ent", "entitlement.apply-event")
    )
    support, _ = world.project_support("ent")
    assert support and support.support_tier == "enterprise-247"

    packaging, _ = world.admit_packaging(
        PackagingEvidence(True, True, True, True, True, True)
    )
    assert packaging

    cancelled = world.cancel_agreement("a", grant=grant("a", "agreement.cancel"))
    assert cancelled.receipt_id
