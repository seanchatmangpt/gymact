"""Provider-neutral post-AGI DfCM commerce world.

This module deliberately stops at the external-provider boundary.  It can execute
and receipt internal commercial semantics, but marketplace acceptance, seller
registration, tax/banking/KYC, and legal agreement execution are evidence inputs,
never simulator-manufactured facts.

The world preserves SELECT -> CONSTRUCT -> DO separation and enforces BRCE for
consequential internal transitions.  A provider adapter can later project this
contract to AWS, Microsoft, Google Cloud, or direct Stripe without changing the
commercial ontology.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import StrEnum
from hashlib import sha256
import json
from typing import Any, Iterable, Mapping, Sequence


class Standing(StrEnum):
    UNKNOWN = "UNKNOWN"
    PARTIAL_ALIVE = "PARTIAL_ALIVE"
    ALIVE = "ALIVE"
    BLOCKED = "BLOCKED"
    BUILD_BROKEN = "BUILD_BROKEN"
    UNSUPPORTED = "UNSUPPORTED"
    REFUSED = "REFUSED"


class OperationKind(StrEnum):
    SELECT = "SELECT"
    CONSTRUCT = "CONSTRUCT"
    DO = "DO"


class BillingAuthority(StrEnum):
    DIRECT = "DIRECT"
    EXTERNAL_COMMERCE = "EXTERNAL_COMMERCE"


class EntitlementState(StrEnum):
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"


class EventKind(StrEnum):
    CREATE = "CREATE"
    ACTIVATE = "ACTIVATE"
    AMEND = "AMEND"
    SUSPEND = "SUSPEND"
    REINSTATE = "REINSTATE"
    RENEW = "RENEW"
    CANCEL = "CANCEL"
    EXPIRE = "EXPIRE"


class RefusalCode(StrEnum):
    MULTIPLE_BILLING_AUTHORITIES = "REFUSED:MULTIPLE_BILLING_AUTHORITIES"
    MISSING_AGREEMENT_ID = "REFUSED:MISSING_AGREEMENT_ID"
    MISSING_ENTITLEMENT_ID = "REFUSED:MISSING_ENTITLEMENT_ID"
    DUPLICATE_OR_STALE_EVENT = "REFUSED:DUPLICATE_OR_STALE_EVENT"
    ILLEGAL_LIFECYCLE_TRANSITION = "REFUSED:ILLEGAL_LIFECYCLE_TRANSITION"
    CROSS_TENANT_ENTITLEMENT = "REFUSED:CROSS_TENANT_ENTITLEMENT"
    USAGE_WITHOUT_ACTIVE_ENTITLEMENT = "REFUSED:USAGE_WITHOUT_ACTIVE_ENTITLEMENT"
    METER_WITHOUT_ADMITTED_USAGE = "REFUSED:METER_WITHOUT_ADMITTED_USAGE"
    SETTLEMENT_WITHOUT_PROVIDER_ACCEPTANCE = (
        "REFUSED:SETTLEMENT_WITHOUT_PROVIDER_ACCEPTANCE"
    )
    PROVIDER_ACCEPTANCE_NOT_OBSERVED = "REFUSED:PROVIDER_ACCEPTANCE_NOT_OBSERVED"
    EXTERNAL_DO_WITHOUT_AUTHORITY = "REFUSED:EXTERNAL_DO_WITHOUT_AUTHORITY"
    BRCE_REQUIRED = "REFUSED:BRCE_REQUIRED"
    RECEIPT_REQUIRED = "REFUSED:RECEIPT_REQUIRED"
    PRICING_DIMENSION_MISMATCH = "REFUSED:PRICING_DIMENSION_MISMATCH"
    ENTITLEMENT_IDENTITY_COLLAPSE = "REFUSED:ENTITLEMENT_IDENTITY_COLLAPSE"
    INCOMPLETE_PACKAGING_EVIDENCE = "REFUSED:INCOMPLETE_PACKAGING_EVIDENCE"


class ExternalBlocker(StrEnum):
    SELLER_REGISTRATION = "seller_registration"
    TAX = "tax"
    BANKING = "banking"
    KYC = "kyc"
    EULA = "eula"
    PROVIDER_REVIEW = "provider_review"
    PROVIDER_ACCEPTANCE = "provider_acceptance"


@dataclass(frozen=True, slots=True)
class Refusal:
    code: RefusalCode
    reason: str


@dataclass(frozen=True, slots=True)
class PricingDimension:
    dimension_id: str
    unit: str
    unit_price_micros: int

    def __post_init__(self) -> None:
        if not self.dimension_id or not self.unit:
            raise ValueError("pricing dimension identity and unit are required")
        if self.unit_price_micros < 0:
            raise ValueError("unit price cannot be negative")


@dataclass(frozen=True, slots=True)
class CommercialAgreement:
    agreement_id: str
    legal_entity_id: str
    account_id: str
    product_id: str
    offer_id: str
    billing_authority: BillingAuthority
    pricing: tuple[PricingDimension, ...]
    effective_at: str
    expires_at: str | None = None
    external_source: str | None = None
    negotiated_terms_ref: str | None = None

    @property
    def pricing_by_id(self) -> dict[str, PricingDimension]:
        return {item.dimension_id: item for item in self.pricing}


@dataclass(frozen=True, slots=True)
class Entitlement:
    entitlement_id: str
    agreement_id: str
    tenant_id: str
    product_id: str
    state: EntitlementState
    quantity: int
    revision: int
    last_event_id: str
    capabilities: frozenset[str] = frozenset()
    support_tier: str | None = None


@dataclass(frozen=True, slots=True)
class EntitlementEvent:
    event_id: str
    source: str
    kind: EventKind
    agreement_id: str
    entitlement_id: str
    tenant_id: str
    product_id: str
    revision: int
    quantity: int = 1
    capabilities: frozenset[str] = frozenset()
    support_tier: str | None = None


@dataclass(frozen=True, slots=True)
class UsageObservation:
    observation_id: str
    entitlement_id: str
    tenant_id: str
    dimension_id: str
    quantity: int
    observed_at: str
    admitted: bool = False


@dataclass(frozen=True, slots=True)
class MeterIntent:
    intent_id: str
    agreement_id: str
    entitlement_id: str
    dimension_id: str
    quantity: int
    observation_ids: tuple[str, ...]
    amount_micros: int
    constructed_receipt: str


@dataclass(frozen=True, slots=True)
class ExternalAcceptance:
    acceptance_id: str
    intent_id: str
    provider: str
    observed: bool
    evidence_ref: str
    accepted_quantity: int


@dataclass(frozen=True, slots=True)
class Settlement:
    settlement_id: str
    intent_id: str
    acceptance_id: str
    amount_micros: int
    receipt: str


@dataclass(frozen=True, slots=True)
class BrokerGrant:
    grant_id: str
    authority: str
    subject_id: str
    allowed_operation: str
    evidence_ref: str


@dataclass(frozen=True, slots=True)
class CommerceReceipt:
    receipt_id: str
    operation: str
    subject_id: str
    authority: str
    consequence_digest: str
    replay_key: str


@dataclass(frozen=True, slots=True)
class PackagingEvidence:
    helm_chart: bool = False
    stable_kubernetes_apis: bool = False
    sbom: bool = False
    vulnerability_scan: bool = False
    signed_provenance: bool = False
    portable_registry_artifact: bool = False

    @property
    def complete(self) -> bool:
        return all(
            (
                self.helm_chart,
                self.stable_kubernetes_apis,
                self.sbom,
                self.vulnerability_scan,
                self.signed_provenance,
                self.portable_registry_artifact,
            )
        )

    @property
    def missing(self) -> tuple[str, ...]:
        values = {
            "helm_chart": self.helm_chart,
            "stable_kubernetes_apis": self.stable_kubernetes_apis,
            "sbom": self.sbom,
            "vulnerability_scan": self.vulnerability_scan,
            "signed_provenance": self.signed_provenance,
            "portable_registry_artifact": self.portable_registry_artifact,
        }
        return tuple(name for name, present in values.items() if not present)


@dataclass(frozen=True, slots=True)
class ReadinessReport:
    internal_standing: Standing
    external_standing: Standing
    missing_packaging: tuple[str, ...]
    external_blockers: tuple[ExternalBlocker, ...]
    findings: tuple[str, ...]

    @property
    def marketplace_ready(self) -> bool:
        return (
            self.internal_standing is Standing.ALIVE
            and self.external_standing is Standing.ALIVE
            and not self.missing_packaging
            and not self.external_blockers
            and not self.findings
        )


@dataclass(frozen=True, slots=True)
class Capability:
    capability_id: str
    operation_kind: OperationKind
    reversible: bool
    external_authority_required: bool
    receipt_required: bool
    description: str


CAPABILITIES: tuple[Capability, ...] = (
    Capability("agreement.admit", OperationKind.CONSTRUCT, True, False, True, "Admit one commercial agreement without collapsing concurrent agreements."),
    Capability("billing-authority.fence", OperationKind.CONSTRUCT, True, False, True, "Require exactly one billing authority for an agreement."),
    Capability("entitlement.apply-event", OperationKind.DO, False, False, True, "Apply source-neutral entitlement lifecycle events through BRCE."),
    Capability("entitlement.concurrent", OperationKind.CONSTRUCT, True, False, True, "Preserve multiple entitlements for one account/product."),
    Capability("entitlement.lifecycle", OperationKind.DO, False, False, True, "Activate, amend, suspend, reinstate, renew, cancel and expire."),
    Capability("identity.bind", OperationKind.CONSTRUCT, True, False, True, "Bind external account identity to tenant identity without granting billing authority."),
    Capability("usage.observe", OperationKind.SELECT, True, False, True, "Observe usage without making it billable."),
    Capability("usage.admit", OperationKind.CONSTRUCT, True, False, True, "Admit usage only against an active entitlement."),
    Capability("meter.construct", OperationKind.CONSTRUCT, True, False, True, "Construct deterministic meter intent from admitted usage."),
    Capability("meter.submit", OperationKind.DO, False, True, True, "Submit meter intent only through an external-authority adapter."),
    Capability("provider.acceptance.admit", OperationKind.CONSTRUCT, True, True, True, "Admit observed provider acceptance; never synthesize it."),
    Capability("settlement.reconcile", OperationKind.CONSTRUCT, True, False, True, "Reconcile accepted provider quantity and price."),
    Capability("agreement.amend", OperationKind.DO, False, False, True, "Apply receipted agreement amendments."),
    Capability("agreement.renew", OperationKind.DO, False, False, True, "Renew without changing agreement identity semantics."),
    Capability("agreement.cancel", OperationKind.DO, False, False, True, "Cancel and fence further usage."),
    Capability("credit.construct", OperationKind.CONSTRUCT, True, False, True, "Construct auditable credit intent."),
    Capability("refund.construct", OperationKind.CONSTRUCT, True, False, True, "Construct auditable refund intent."),
    Capability("support.entitle", OperationKind.CONSTRUCT, True, False, True, "Project support/SLA tier from entitlement."),
    Capability("pricing.validate", OperationKind.CONSTRUCT, True, False, True, "Reject dimensions absent from the agreement."),
    Capability("replay.idempotent", OperationKind.CONSTRUCT, True, False, True, "Reject duplicate/stale commercial events."),
    Capability("packaging.helm", OperationKind.CONSTRUCT, True, False, True, "Require Helm as a portable deployment projection."),
    Capability("packaging.k8s-stable-api", OperationKind.CONSTRUCT, True, False, True, "Reject alpha/deprecated Kubernetes APIs at the portability boundary."),
    Capability("supply-chain.sbom", OperationKind.CONSTRUCT, True, False, True, "Require SBOM evidence."),
    Capability("supply-chain.vulnerability-scan", OperationKind.CONSTRUCT, True, False, True, "Require vulnerability scan evidence."),
    Capability("supply-chain.provenance", OperationKind.CONSTRUCT, True, False, True, "Require signed artifact provenance."),
    Capability("artifact.portable-registry", OperationKind.CONSTRUCT, True, False, True, "Require registry-neutral publishable artifact identity."),
    Capability("external.seller-registration", OperationKind.DO, False, True, True, "External evidence only."),
    Capability("external.kyc", OperationKind.DO, False, True, True, "External evidence only."),
    Capability("external.tax", OperationKind.DO, False, True, True, "External evidence only."),
    Capability("external.banking", OperationKind.DO, False, True, True, "External evidence only."),
    Capability("external.eula", OperationKind.DO, False, True, True, "External legal authority only."),
    Capability("external.provider-review", OperationKind.DO, False, True, True, "External provider authority only."),
)


_TRANSITIONS: dict[EntitlementState, dict[EventKind, EntitlementState]] = {
    EntitlementState.PENDING: {
        EventKind.ACTIVATE: EntitlementState.ACTIVE,
        EventKind.CANCEL: EntitlementState.CANCELLED,
    },
    EntitlementState.ACTIVE: {
        EventKind.AMEND: EntitlementState.ACTIVE,
        EventKind.SUSPEND: EntitlementState.SUSPENDED,
        EventKind.RENEW: EntitlementState.ACTIVE,
        EventKind.CANCEL: EntitlementState.CANCELLED,
        EventKind.EXPIRE: EntitlementState.EXPIRED,
    },
    EntitlementState.SUSPENDED: {
        EventKind.REINSTATE: EntitlementState.ACTIVE,
        EventKind.CANCEL: EntitlementState.CANCELLED,
        EventKind.EXPIRE: EntitlementState.EXPIRED,
    },
    EntitlementState.CANCELLED: {},
    EntitlementState.EXPIRED: {},
}


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _digest(value: Any) -> str:
    return sha256(_canonical(value).encode()).hexdigest()


def _receipt(
    *,
    operation: str,
    subject_id: str,
    authority: str,
    consequence: Mapping[str, Any],
    replay_key: str,
) -> CommerceReceipt:
    digest = _digest(consequence)
    rid = _digest(
        {
            "operation": operation,
            "subject_id": subject_id,
            "authority": authority,
            "consequence_digest": digest,
            "replay_key": replay_key,
        }
    )
    return CommerceReceipt(
        receipt_id=rid,
        operation=operation,
        subject_id=subject_id,
        authority=authority,
        consequence_digest=digest,
        replay_key=replay_key,
    )


@dataclass(slots=True)
class CommerceWorld:
    agreements: dict[str, CommercialAgreement] = field(default_factory=dict)
    entitlements: dict[str, Entitlement] = field(default_factory=dict)
    usage: dict[str, UsageObservation] = field(default_factory=dict)
    meter_intents: dict[str, MeterIntent] = field(default_factory=dict)
    acceptances: dict[str, ExternalAcceptance] = field(default_factory=dict)
    settlements: dict[str, Settlement] = field(default_factory=dict)
    processed_events: set[str] = field(default_factory=set)
    receipts: dict[str, CommerceReceipt] = field(default_factory=dict)
    external_evidence: dict[ExternalBlocker, str] = field(default_factory=dict)

    def admit_agreement(
        self, agreement: CommercialAgreement
    ) -> tuple[CommercialAgreement | None, CommerceReceipt | Refusal]:
        if not agreement.agreement_id:
            return None, Refusal(RefusalCode.MISSING_AGREEMENT_ID, "agreement_id is required")
        existing = self.agreements.get(agreement.agreement_id)
        if existing and existing.billing_authority is not agreement.billing_authority:
            return None, Refusal(
                RefusalCode.MULTIPLE_BILLING_AUTHORITIES,
                f"{agreement.agreement_id} already bound to {existing.billing_authority}",
            )
        dimensions = [item.dimension_id for item in agreement.pricing]
        if len(dimensions) != len(set(dimensions)):
            return None, Refusal(
                RefusalCode.PRICING_DIMENSION_MISMATCH,
                "pricing dimensions must be unique within an agreement",
            )
        self.agreements[agreement.agreement_id] = agreement
        receipt = _receipt(
            operation="agreement.admit",
            subject_id=agreement.agreement_id,
            authority="commerce-kernel",
            consequence={
                "billing_authority": agreement.billing_authority,
                "pricing": dimensions,
                "account_id": agreement.account_id,
                "product_id": agreement.product_id,
            },
            replay_key=f"agreement:{agreement.agreement_id}",
        )
        self.receipts[receipt.receipt_id] = receipt
        return agreement, receipt

    def _brce(
        self,
        *,
        operation: str,
        subject_id: str,
        grant: BrokerGrant | None,
        consequence: Mapping[str, Any],
        replay_key: str,
    ) -> CommerceReceipt | Refusal:
        if grant is None:
            return Refusal(RefusalCode.BRCE_REQUIRED, f"{operation} requires broker grant")
        if grant.subject_id != subject_id or grant.allowed_operation != operation:
            return Refusal(
                RefusalCode.BRCE_REQUIRED,
                f"grant {grant.grant_id} does not authorize {operation} on {subject_id}",
            )
        receipt = _receipt(
            operation=operation,
            subject_id=subject_id,
            authority=grant.authority,
            consequence=consequence,
            replay_key=replay_key,
        )
        self.receipts[receipt.receipt_id] = receipt
        return receipt

    def apply_entitlement_event(
        self,
        source: str,
        event: EntitlementEvent,
        *,
        grant: BrokerGrant | None,
    ) -> tuple[Entitlement | None, CommerceReceipt | Refusal]:
        if source != event.source:
            return None, Refusal(
                RefusalCode.EXTERNAL_DO_WITHOUT_AUTHORITY,
                "declared event source must equal routed source",
            )
        if not event.entitlement_id:
            return None, Refusal(
                RefusalCode.MISSING_ENTITLEMENT_ID, "entitlement_id is required"
            )
        agreement = self.agreements.get(event.agreement_id)
        if agreement is None:
            return None, Refusal(
                RefusalCode.MISSING_AGREEMENT_ID,
                f"unknown agreement {event.agreement_id}",
            )
        if event.event_id in self.processed_events:
            return None, Refusal(
                RefusalCode.DUPLICATE_OR_STALE_EVENT,
                f"event {event.event_id} was already applied",
            )
        if event.product_id != agreement.product_id:
            return None, Refusal(
                RefusalCode.CROSS_TENANT_ENTITLEMENT,
                "event product does not belong to agreement",
            )

        current = self.entitlements.get(event.entitlement_id)
        if current is None:
            if event.kind is not EventKind.CREATE or event.revision != 1:
                return None, Refusal(
                    RefusalCode.ILLEGAL_LIFECYCLE_TRANSITION,
                    "new entitlement requires CREATE revision 1",
                )
            target = EntitlementState.PENDING
        else:
            if current.agreement_id != event.agreement_id or current.tenant_id != event.tenant_id:
                return None, Refusal(
                    RefusalCode.CROSS_TENANT_ENTITLEMENT,
                    "entitlement identity cannot move across agreement/tenant",
                )
            if event.revision <= current.revision:
                return None, Refusal(
                    RefusalCode.DUPLICATE_OR_STALE_EVENT,
                    f"revision {event.revision} is not newer than {current.revision}",
                )
            target = _TRANSITIONS[current.state].get(event.kind)
            if target is None:
                return None, Refusal(
                    RefusalCode.ILLEGAL_LIFECYCLE_TRANSITION,
                    f"{current.state} cannot apply {event.kind}",
                )

        candidate = Entitlement(
            entitlement_id=event.entitlement_id,
            agreement_id=event.agreement_id,
            tenant_id=event.tenant_id,
            product_id=event.product_id,
            state=target,
            quantity=event.quantity,
            revision=event.revision,
            last_event_id=event.event_id,
            capabilities=event.capabilities,
            support_tier=event.support_tier,
        )
        consequence = {
            "state": candidate.state,
            "revision": candidate.revision,
            "quantity": candidate.quantity,
            "capabilities": sorted(candidate.capabilities),
        }
        receipt = self._brce(
            operation="entitlement.apply-event",
            subject_id=event.entitlement_id,
            grant=grant,
            consequence=consequence,
            replay_key=f"event:{event.event_id}",
        )
        if isinstance(receipt, Refusal):
            return None, receipt

        self.entitlements[event.entitlement_id] = candidate
        self.processed_events.add(event.event_id)
        return candidate, receipt

    def observe_usage(self, observation: UsageObservation) -> CommerceReceipt:
        self.usage[observation.observation_id] = replace(observation, admitted=False)
        receipt = _receipt(
            operation="usage.observe",
            subject_id=observation.observation_id,
            authority="observation",
            consequence={
                "entitlement_id": observation.entitlement_id,
                "dimension_id": observation.dimension_id,
                "quantity": observation.quantity,
            },
            replay_key=f"usage:{observation.observation_id}",
        )
        self.receipts[receipt.receipt_id] = receipt
        return receipt

    def admit_usage(
        self, observation_id: str
    ) -> tuple[UsageObservation | None, CommerceReceipt | Refusal]:
        observation = self.usage[observation_id]
        entitlement = self.entitlements.get(observation.entitlement_id)
        if entitlement is None or entitlement.state is not EntitlementState.ACTIVE:
            return None, Refusal(
                RefusalCode.USAGE_WITHOUT_ACTIVE_ENTITLEMENT,
                f"{observation.entitlement_id} is not active",
            )
        if entitlement.tenant_id != observation.tenant_id:
            return None, Refusal(
                RefusalCode.CROSS_TENANT_ENTITLEMENT,
                "usage tenant does not own entitlement",
            )
        agreement = self.agreements[entitlement.agreement_id]
        if observation.dimension_id not in agreement.pricing_by_id:
            return None, Refusal(
                RefusalCode.PRICING_DIMENSION_MISMATCH,
                f"{observation.dimension_id} not present in agreement",
            )
        admitted = replace(observation, admitted=True)
        self.usage[observation_id] = admitted
        receipt = _receipt(
            operation="usage.admit",
            subject_id=observation_id,
            authority="commerce-kernel",
            consequence={"admitted": True, "entitlement_id": observation.entitlement_id},
            replay_key=f"usage-admit:{observation_id}",
        )
        self.receipts[receipt.receipt_id] = receipt
        return admitted, receipt

    def construct_meter_intent(
        self,
        *,
        intent_id: str,
        observation_ids: Sequence[str],
    ) -> tuple[MeterIntent | None, CommerceReceipt | Refusal]:
        observations = [self.usage[item] for item in observation_ids]
        if not observations or any(not item.admitted for item in observations):
            return None, Refusal(
                RefusalCode.METER_WITHOUT_ADMITTED_USAGE,
                "every meter input must be admitted usage",
            )
        entitlement_ids = {item.entitlement_id for item in observations}
        dimensions = {item.dimension_id for item in observations}
        if len(entitlement_ids) != 1 or len(dimensions) != 1:
            return None, Refusal(
                RefusalCode.METER_WITHOUT_ADMITTED_USAGE,
                "one meter intent must bind exactly one entitlement and dimension",
            )
        entitlement_id = next(iter(entitlement_ids))
        dimension = next(iter(dimensions))
        entitlement = self.entitlements[entitlement_id]
        agreement = self.agreements[entitlement.agreement_id]
        pricing = agreement.pricing_by_id.get(dimension)
        if pricing is None:
            return None, Refusal(
                RefusalCode.PRICING_DIMENSION_MISMATCH,
                f"{dimension} not priced by agreement",
            )
        quantity = sum(item.quantity for item in observations)
        amount = quantity * pricing.unit_price_micros
        construct_receipt = _receipt(
            operation="meter.construct",
            subject_id=intent_id,
            authority="commerce-kernel",
            consequence={
                "agreement_id": agreement.agreement_id,
                "entitlement_id": entitlement_id,
                "dimension_id": dimension,
                "quantity": quantity,
                "amount_micros": amount,
                "observations": sorted(observation_ids),
            },
            replay_key=f"meter:{intent_id}",
        )
        self.receipts[construct_receipt.receipt_id] = construct_receipt
        intent = MeterIntent(
            intent_id=intent_id,
            agreement_id=agreement.agreement_id,
            entitlement_id=entitlement_id,
            dimension_id=dimension,
            quantity=quantity,
            observation_ids=tuple(sorted(observation_ids)),
            amount_micros=amount,
            constructed_receipt=construct_receipt.receipt_id,
        )
        self.meter_intents[intent_id] = intent
        return intent, construct_receipt

    def admit_external_acceptance(
        self, acceptance: ExternalAcceptance
    ) -> tuple[ExternalAcceptance | None, CommerceReceipt | Refusal]:
        if not acceptance.observed or not acceptance.evidence_ref:
            return None, Refusal(
                RefusalCode.PROVIDER_ACCEPTANCE_NOT_OBSERVED,
                "provider acceptance must be observed external evidence",
            )
        intent = self.meter_intents.get(acceptance.intent_id)
        if intent is None:
            return None, Refusal(
                RefusalCode.METER_WITHOUT_ADMITTED_USAGE,
                f"unknown meter intent {acceptance.intent_id}",
            )
        self.acceptances[acceptance.acceptance_id] = acceptance
        receipt = _receipt(
            operation="provider.acceptance.admit",
            subject_id=acceptance.acceptance_id,
            authority=acceptance.provider,
            consequence={
                "intent_id": acceptance.intent_id,
                "accepted_quantity": acceptance.accepted_quantity,
                "evidence_ref": acceptance.evidence_ref,
            },
            replay_key=f"acceptance:{acceptance.acceptance_id}",
        )
        self.receipts[receipt.receipt_id] = receipt
        return acceptance, receipt

    def reconcile(
        self, *, settlement_id: str, acceptance_id: str
    ) -> tuple[Settlement | None, CommerceReceipt | Refusal]:
        acceptance = self.acceptances.get(acceptance_id)
        if acceptance is None:
            return None, Refusal(
                RefusalCode.SETTLEMENT_WITHOUT_PROVIDER_ACCEPTANCE,
                f"{acceptance_id} has no admitted provider acceptance",
            )
        intent = self.meter_intents[acceptance.intent_id]
        if acceptance.accepted_quantity != intent.quantity:
            return None, Refusal(
                RefusalCode.SETTLEMENT_WITHOUT_PROVIDER_ACCEPTANCE,
                "provider quantity differs from constructed meter quantity",
            )
        receipt = _receipt(
            operation="settlement.reconcile",
            subject_id=settlement_id,
            authority="commerce-kernel",
            consequence={
                "intent_id": intent.intent_id,
                "acceptance_id": acceptance.acceptance_id,
                "amount_micros": intent.amount_micros,
            },
            replay_key=f"settlement:{settlement_id}",
        )
        self.receipts[receipt.receipt_id] = receipt
        settlement = Settlement(
            settlement_id=settlement_id,
            intent_id=intent.intent_id,
            acceptance_id=acceptance.acceptance_id,
            amount_micros=intent.amount_micros,
            receipt=receipt.receipt_id,
        )
        self.settlements[settlement_id] = settlement
        return settlement, receipt

    def admit_external_blocker_evidence(
        self, blocker: ExternalBlocker, evidence_ref: str
    ) -> CommerceReceipt | Refusal:
        if not evidence_ref:
            return Refusal(
                RefusalCode.PROVIDER_ACCEPTANCE_NOT_OBSERVED,
                f"{blocker} requires an external evidence reference",
            )
        self.external_evidence[blocker] = evidence_ref
        receipt = _receipt(
            operation="external-evidence.admit",
            subject_id=blocker,
            authority="external",
            consequence={"evidence_ref": evidence_ref},
            replay_key=f"external:{blocker}:{evidence_ref}",
        )
        self.receipts[receipt.receipt_id] = receipt
        return receipt

    def assert_identity_preservation(self) -> Refusal | None:
        """Refuse any collapse of distinct concurrent agreement/entitlement identities."""
        by_account_product: dict[tuple[str, str], set[str]] = {}
        for agreement in self.agreements.values():
            by_account_product.setdefault(
                (agreement.account_id, agreement.product_id), set()
            ).add(agreement.agreement_id)
        # Multiple agreements are lawful; each entitlement must still point to an exact agreement.
        for entitlement in self.entitlements.values():
            if entitlement.agreement_id not in self.agreements:
                return Refusal(
                    RefusalCode.ENTITLEMENT_IDENTITY_COLLAPSE,
                    f"{entitlement.entitlement_id} lost exact agreement identity",
                )
        return None

    def readiness(
        self,
        packaging: PackagingEvidence,
        *,
        required_external: Iterable[ExternalBlocker] = tuple(ExternalBlocker),
    ) -> ReadinessReport:
        findings: list[str] = []
        identity = self.assert_identity_preservation()
        if identity:
            findings.append(identity.code)
        # Internal standing is earned only when the core path has actually executed.
        internal_executed = bool(
            self.agreements
            and self.entitlements
            and any(item.state is EntitlementState.ACTIVE for item in self.entitlements.values())
            and any(item.admitted for item in self.usage.values())
            and self.meter_intents
            and self.receipts
        )
        internal = Standing.ALIVE if internal_executed and packaging.complete and not findings else Standing.PARTIAL_ALIVE
        missing_external = tuple(
            blocker for blocker in required_external if blocker not in self.external_evidence
        )
        external = Standing.ALIVE if not missing_external else Standing.BLOCKED
        return ReadinessReport(
            internal_standing=internal,
            external_standing=external,
            missing_packaging=packaging.missing,
            external_blockers=missing_external,
            findings=tuple(findings),
        )


def capability_digest() -> str:
    """Stable class-closure digest for a later ggen-marketplace pack binding."""
    return _digest(
        [
            {
                "id": item.capability_id,
                "operation": item.operation_kind,
                "reversible": item.reversible,
                "external_authority_required": item.external_authority_required,
                "receipt_required": item.receipt_required,
                "description": item.description,
            }
            for item in CAPABILITIES
        ]
    )
