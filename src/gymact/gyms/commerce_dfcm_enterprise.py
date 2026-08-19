"""Enterprise closure for the provider-neutral DfCM commerce world.

This module turns the capability catalog into an executable surface. It extends
the kernel without introducing any marketplace SDK or external DO authority.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Mapping

from gymact.gyms.commerce_dfcm import (
    CAPABILITIES,
    BrokerGrant,
    CommerceReceipt,
    CommerceWorld,
    CommercialAgreement,
    OperationKind,
    PackagingEvidence,
    PricingDimension,
    Refusal,
    RefusalCode,
    _receipt,
)


@dataclass(frozen=True, slots=True)
class IdentityBinding:
    binding_id: str
    account_id: str
    tenant_id: str
    issuer: str
    subject: str
    receipt: str


@dataclass(frozen=True, slots=True)
class FinancialAdjustment:
    adjustment_id: str
    agreement_id: str
    kind: str
    amount_micros: int
    reason: str
    receipt: str


@dataclass(frozen=True, slots=True)
class SupportProjection:
    entitlement_id: str
    tenant_id: str
    support_tier: str
    capabilities: tuple[str, ...]
    receipt: str


@dataclass(frozen=True, slots=True)
class PackagingAdmission:
    evidence: PackagingEvidence
    receipt: str


@dataclass(slots=True)
class EnterpriseCommerceWorld(CommerceWorld):
    identity_bindings: dict[str, IdentityBinding] = field(default_factory=dict)
    agreement_revisions: dict[str, int] = field(default_factory=dict)
    agreement_status: dict[str, str] = field(default_factory=dict)
    adjustments: dict[str, FinancialAdjustment] = field(default_factory=dict)
    support_projections: dict[str, SupportProjection] = field(default_factory=dict)
    packaging_admission: PackagingAdmission | None = None

    def admit_agreement(
        self, agreement: CommercialAgreement
    ) -> tuple[CommercialAgreement | None, CommerceReceipt | Refusal]:
        admitted, evidence = CommerceWorld.admit_agreement(self, agreement)
        if admitted is not None:
            self.agreement_revisions.setdefault(agreement.agreement_id, 1)
            self.agreement_status.setdefault(agreement.agreement_id, "ACTIVE")
        return admitted, evidence

    def bind_identity(
        self,
        *,
        binding_id: str,
        account_id: str,
        tenant_id: str,
        issuer: str,
        subject: str,
    ) -> tuple[IdentityBinding | None, CommerceReceipt | Refusal]:
        if not all((binding_id, account_id, tenant_id, issuer, subject)):
            return None, Refusal(
                RefusalCode.CROSS_TENANT_ENTITLEMENT,
                "identity binding requires exact account/tenant/issuer/subject",
            )
        for binding in self.identity_bindings.values():
            if binding.issuer == issuer and binding.subject == subject:
                if binding.tenant_id != tenant_id or binding.account_id != account_id:
                    return None, Refusal(
                        RefusalCode.CROSS_TENANT_ENTITLEMENT,
                        "external subject already bound to another account/tenant",
                    )
        evidence = self._store(
            _receipt(
                "identity.bind",
                binding_id,
                "commerce-kernel",
                {
                    "account": account_id,
                    "tenant": tenant_id,
                    "issuer": issuer,
                    "subject": subject,
                },
                f"identity:{binding_id}",
            )
        )
        binding = IdentityBinding(
            binding_id,
            account_id,
            tenant_id,
            issuer,
            subject,
            evidence.receipt_id,
        )
        self.identity_bindings[binding_id] = binding
        return binding, evidence

    def amend_agreement(
        self,
        agreement_id: str,
        *,
        pricing: tuple[PricingDimension, ...],
        offer_id: str,
        grant: BrokerGrant | None,
    ) -> tuple[CommercialAgreement | None, CommerceReceipt | Refusal]:
        current = self.agreements.get(agreement_id)
        if current is None:
            return None, Refusal(RefusalCode.MISSING_AGREEMENT_ID, "unknown agreement")
        if self.agreement_status.get(agreement_id) == "CANCELLED":
            return None, Refusal(
                RefusalCode.ILLEGAL_LIFECYCLE_TRANSITION,
                "cancelled agreement cannot be amended",
            )
        revision = self.agreement_revisions.get(agreement_id, 1) + 1
        candidate = replace(current, pricing=pricing, offer_id=offer_id)
        evidence = self._brce(
            "agreement.amend",
            agreement_id,
            grant,
            {
                "revision": revision,
                "offer_id": offer_id,
                "pricing": [item.dimension_id for item in pricing],
            },
            f"agreement-amend:{agreement_id}:{revision}",
        )
        if isinstance(evidence, Refusal):
            return None, evidence
        self.agreements[agreement_id] = candidate
        self.agreement_revisions[agreement_id] = revision
        return candidate, evidence

    def renew_agreement(
        self,
        agreement_id: str,
        *,
        expires_at: str,
        grant: BrokerGrant | None,
    ) -> tuple[CommercialAgreement | None, CommerceReceipt | Refusal]:
        current = self.agreements.get(agreement_id)
        if current is None:
            return None, Refusal(RefusalCode.MISSING_AGREEMENT_ID, "unknown agreement")
        if self.agreement_status.get(agreement_id) == "CANCELLED":
            return None, Refusal(
                RefusalCode.ILLEGAL_LIFECYCLE_TRANSITION,
                "cancelled agreement cannot be renewed",
            )
        revision = self.agreement_revisions.get(agreement_id, 1) + 1
        candidate = replace(current, expires_at=expires_at)
        evidence = self._brce(
            "agreement.renew",
            agreement_id,
            grant,
            {"revision": revision, "expires_at": expires_at},
            f"agreement-renew:{agreement_id}:{revision}",
        )
        if isinstance(evidence, Refusal):
            return None, evidence
        self.agreements[agreement_id] = candidate
        self.agreement_revisions[agreement_id] = revision
        return candidate, evidence

    def cancel_agreement(
        self,
        agreement_id: str,
        *,
        grant: BrokerGrant | None,
    ) -> CommerceReceipt | Refusal:
        if agreement_id not in self.agreements:
            return Refusal(RefusalCode.MISSING_AGREEMENT_ID, "unknown agreement")
        if self.agreement_status.get(agreement_id) == "CANCELLED":
            return Refusal(
                RefusalCode.DUPLICATE_OR_STALE_EVENT,
                "agreement already cancelled",
            )
        evidence = self._brce(
            "agreement.cancel",
            agreement_id,
            grant,
            {"status": "CANCELLED"},
            f"agreement-cancel:{agreement_id}",
        )
        if isinstance(evidence, Refusal):
            return evidence
        self.agreement_status[agreement_id] = "CANCELLED"
        return evidence

    def _construct_adjustment(
        self,
        *,
        adjustment_id: str,
        agreement_id: str,
        kind: str,
        amount_micros: int,
        reason: str,
    ) -> tuple[FinancialAdjustment | None, CommerceReceipt | Refusal]:
        if agreement_id not in self.agreements:
            return None, Refusal(RefusalCode.MISSING_AGREEMENT_ID, "unknown agreement")
        if amount_micros <= 0:
            return None, Refusal(
                RefusalCode.PRICING_DIMENSION_MISMATCH,
                "adjustment amount must be positive",
            )
        evidence = self._store(
            _receipt(
                f"{kind}.construct",
                adjustment_id,
                "commerce-kernel",
                {
                    "agreement": agreement_id,
                    "amount_micros": amount_micros,
                    "reason": reason,
                },
                f"{kind}:{adjustment_id}",
            )
        )
        adjustment = FinancialAdjustment(
            adjustment_id,
            agreement_id,
            kind,
            amount_micros,
            reason,
            evidence.receipt_id,
        )
        self.adjustments[adjustment_id] = adjustment
        return adjustment, evidence

    def construct_credit(
        self, **kwargs: object
    ) -> tuple[FinancialAdjustment | None, CommerceReceipt | Refusal]:
        return self._construct_adjustment(kind="credit", **kwargs)

    def construct_refund(
        self, **kwargs: object
    ) -> tuple[FinancialAdjustment | None, CommerceReceipt | Refusal]:
        return self._construct_adjustment(kind="refund", **kwargs)

    def project_support(
        self, entitlement_id: str
    ) -> tuple[SupportProjection | None, CommerceReceipt | Refusal]:
        entitlement = self.entitlements.get(entitlement_id)
        if entitlement is None or not entitlement.support_tier:
            return None, Refusal(
                RefusalCode.MISSING_ENTITLEMENT_ID,
                "support projection requires entitled support tier",
            )
        evidence = self._store(
            _receipt(
                "support.entitle",
                entitlement_id,
                "commerce-kernel",
                {
                    "tenant": entitlement.tenant_id,
                    "support_tier": entitlement.support_tier,
                    "capabilities": sorted(entitlement.capabilities),
                },
                f"support:{entitlement_id}:{entitlement.revision}",
            )
        )
        projection = SupportProjection(
            entitlement_id,
            entitlement.tenant_id,
            entitlement.support_tier,
            tuple(sorted(entitlement.capabilities)),
            evidence.receipt_id,
        )
        self.support_projections[entitlement_id] = projection
        return projection, evidence

    def admit_packaging(
        self, evidence: PackagingEvidence
    ) -> tuple[PackagingAdmission | None, CommerceReceipt | Refusal]:
        if not evidence.complete:
            return None, Refusal(
                RefusalCode.PRICING_DIMENSION_MISMATCH,
                f"packaging evidence incomplete: {','.join(evidence.missing)}",
            )
        receipt = self._store(
            _receipt(
                "packaging.admit",
                "portable-artifact",
                "commerce-kernel",
                {"complete": True, "requirements": 6},
                "packaging:portable-artifact",
            )
        )
        admission = PackagingAdmission(evidence, receipt.receipt_id)
        self.packaging_admission = admission
        return admission, receipt


INTERNAL_CAPABILITY_HANDLERS: Mapping[str, str] = {
    "agreement.admit": "admit_agreement",
    "billing-authority.fence": "admit_agreement",
    "entitlement.apply-event": "apply_entitlement_event",
    "entitlement.concurrent": "assert_identity_preservation",
    "entitlement.lifecycle": "apply_entitlement_event",
    "identity.bind": "bind_identity",
    "usage.observe": "observe_usage",
    "usage.admit": "admit_usage",
    "meter.construct": "construct_meter_intent",
    "provider.acceptance.admit": "admit_external_acceptance",
    "settlement.reconcile": "reconcile",
    "agreement.amend": "amend_agreement",
    "agreement.renew": "renew_agreement",
    "agreement.cancel": "cancel_agreement",
    "credit.construct": "construct_credit",
    "refund.construct": "construct_refund",
    "support.entitle": "project_support",
    "pricing.validate": "admit_usage",
    "replay.idempotent": "apply_entitlement_event",
    "packaging.helm": "admit_packaging",
    "packaging.k8s-stable-api": "admit_packaging",
    "supply-chain.sbom": "admit_packaging",
    "supply-chain.vulnerability-scan": "admit_packaging",
    "supply-chain.provenance": "admit_packaging",
    "artifact.portable-registry": "admit_packaging",
}


def missing_internal_handlers() -> tuple[str, ...]:
    external_only = {
        capability.capability_id
        for capability in CAPABILITIES
        if capability.operation_kind is OperationKind.DO
        and capability.external_authority_required
    }
    expected = {
        capability.capability_id
        for capability in CAPABILITIES
        if capability.capability_id not in external_only
    }
    expected.discard("meter.submit")
    return tuple(sorted(expected - INTERNAL_CAPABILITY_HANDLERS.keys()))
