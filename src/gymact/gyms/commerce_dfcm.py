"""Provider-neutral post-AGI DfCM commerce world.

The gym executes commercial semantics without pretending to be a cloud
marketplace. Provider acceptance and seller/legal facts are admitted only when
their origin is LIVE_EXTERNAL. Fixtures can exercise shape, never external
standing.
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


class EvidenceOrigin(StrEnum):
    FIXTURE = "FIXTURE"
    LIVE_EXTERNAL = "LIVE_EXTERNAL"


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
    PRICING_DIMENSION_MISMATCH = "REFUSED:PRICING_DIMENSION_MISMATCH"
    ENTITLEMENT_IDENTITY_COLLAPSE = "REFUSED:ENTITLEMENT_IDENTITY_COLLAPSE"


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
    evidence_origin: EvidenceOrigin = EvidenceOrigin.FIXTURE


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
        fields = (
            "helm_chart",
            "stable_kubernetes_apis",
            "sbom",
            "vulnerability_scan",
            "signed_provenance",
            "portable_registry_artifact",
        )
        return tuple(name for name in fields if not getattr(self, name))


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


def _cap(
    capability_id: str,
    kind: OperationKind,
    reversible: bool,
    external: bool,
    description: str,
) -> Capability:
    return Capability(capability_id, kind, reversible, external, True, description)


CAPABILITIES = (
    _cap("agreement.admit", OperationKind.CONSTRUCT, True, False, "Admit agreement."),
    _cap("billing-authority.fence", OperationKind.CONSTRUCT, True, False, "One authority."),
    _cap("entitlement.apply-event", OperationKind.DO, False, False, "BRCE lifecycle."),
    _cap("entitlement.concurrent", OperationKind.CONSTRUCT, True, False, "No ID collapse."),
    _cap("entitlement.lifecycle", OperationKind.DO, False, False, "Full lifecycle."),
    _cap("identity.bind", OperationKind.CONSTRUCT, True, False, "External identity binding."),
    _cap("usage.observe", OperationKind.SELECT, True, False, "Observe only."),
    _cap("usage.admit", OperationKind.CONSTRUCT, True, False, "Admit active usage."),
    _cap("meter.construct", OperationKind.CONSTRUCT, True, False, "Meter intent."),
    _cap("meter.submit", OperationKind.DO, False, True, "External submission."),
    _cap("provider.acceptance.admit", OperationKind.CONSTRUCT, True, True, "Observed only."),
    _cap("settlement.reconcile", OperationKind.CONSTRUCT, True, False, "Reconcile."),
    _cap("agreement.amend", OperationKind.DO, False, False, "Amend."),
    _cap("agreement.renew", OperationKind.DO, False, False, "Renew."),
    _cap("agreement.cancel", OperationKind.DO, False, False, "Cancel."),
    _cap("credit.construct", OperationKind.CONSTRUCT, True, False, "Credit intent."),
    _cap("refund.construct", OperationKind.CONSTRUCT, True, False, "Refund intent."),
    _cap("support.entitle", OperationKind.CONSTRUCT, True, False, "Support/SLA."),
    _cap("pricing.validate", OperationKind.CONSTRUCT, True, False, "Pricing dimensions."),
    _cap("replay.idempotent", OperationKind.CONSTRUCT, True, False, "Replay fence."),
    _cap("packaging.helm", OperationKind.CONSTRUCT, True, False, "Helm projection."),
    _cap("packaging.k8s-stable-api", OperationKind.CONSTRUCT, True, False, "Stable APIs."),
    _cap("supply-chain.sbom", OperationKind.CONSTRUCT, True, False, "SBOM."),
    _cap("supply-chain.vulnerability-scan", OperationKind.CONSTRUCT, True, False, "Scan."),
    _cap("supply-chain.provenance", OperationKind.CONSTRUCT, True, False, "Provenance."),
    _cap("artifact.portable-registry", OperationKind.CONSTRUCT, True, False, "Registry-neutral."),
    _cap("external.seller-registration", OperationKind.DO, False, True, "External evidence."),
    _cap("external.kyc", OperationKind.DO, False, True, "External evidence."),
    _cap("external.tax", OperationKind.DO, False, True, "External evidence."),
    _cap("external.banking", OperationKind.DO, False, True, "External evidence."),
    _cap("external.eula", OperationKind.DO, False, True, "External legal authority."),
    _cap("external.provider-review", OperationKind.DO, False, True, "Provider authority."),
)


_TRANSITIONS = {
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
    operation: str,
    subject_id: str,
    authority: str,
    consequence: Mapping[str, Any],
    replay_key: str,
) -> CommerceReceipt:
    consequence_digest = _digest(consequence)
    payload = {
        "operation": operation,
        "subject": subject_id,
        "authority": authority,
        "consequence": consequence_digest,
        "replay": replay_key,
    }
    return CommerceReceipt(
        _digest(payload),
        operation,
        subject_id,
        authority,
        consequence_digest,
        replay_key,
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
    external_evidence: dict[ExternalBlocker, tuple[str, EvidenceOrigin]] = field(
        default_factory=dict
    )

    def _store(self, receipt: CommerceReceipt) -> CommerceReceipt:
        self.receipts[receipt.receipt_id] = receipt
        return receipt

    def admit_agreement(
        self, agreement: CommercialAgreement
    ) -> tuple[CommercialAgreement | None, CommerceReceipt | Refusal]:
        if not agreement.agreement_id:
            return None, Refusal(RefusalCode.MISSING_AGREEMENT_ID, "agreement_id required")
        existing = self.agreements.get(agreement.agreement_id)
        if existing and existing.billing_authority is not agreement.billing_authority:
            return None, Refusal(
                RefusalCode.MULTIPLE_BILLING_AUTHORITIES,
                "agreement already has a different billing authority",
            )
        dimensions = [item.dimension_id for item in agreement.pricing]
        if len(dimensions) != len(set(dimensions)):
            return None, Refusal(
                RefusalCode.PRICING_DIMENSION_MISMATCH,
                "pricing dimensions must be unique",
            )
        self.agreements[agreement.agreement_id] = agreement
        receipt = self._store(
            _receipt(
                "agreement.admit",
                agreement.agreement_id,
                "commerce-kernel",
                {
                    "authority": agreement.billing_authority,
                    "account": agreement.account_id,
                    "product": agreement.product_id,
                    "pricing": dimensions,
                },
                f"agreement:{agreement.agreement_id}",
            )
        )
        return agreement, receipt

    def _brce(
        self,
        operation: str,
        subject_id: str,
        grant: BrokerGrant | None,
        consequence: Mapping[str, Any],
        replay_key: str,
    ) -> CommerceReceipt | Refusal:
        if grant is None:
            return Refusal(RefusalCode.BRCE_REQUIRED, f"{operation} requires BRCE")
        if grant.subject_id != subject_id or grant.allowed_operation != operation:
            return Refusal(RefusalCode.BRCE_REQUIRED, "broker grant does not match operation")
        return self._store(
            _receipt(operation, subject_id, grant.authority, consequence, replay_key)
        )

    def apply_entitlement_event(
        self,
        source: str,
        event: EntitlementEvent,
        *,
        grant: BrokerGrant | None,
    ) -> tuple[Entitlement | None, CommerceReceipt | Refusal]:
        if source != event.source:
            return None, Refusal(
                RefusalCode.EXTERNAL_DO_WITHOUT_AUTHORITY, "routed source mismatch"
            )
        if not event.entitlement_id:
            return None, Refusal(RefusalCode.MISSING_ENTITLEMENT_ID, "id required")
        agreement = self.agreements.get(event.agreement_id)
        if agreement is None:
            return None, Refusal(RefusalCode.MISSING_AGREEMENT_ID, "unknown agreement")
        if event.event_id in self.processed_events:
            return None, Refusal(RefusalCode.DUPLICATE_OR_STALE_EVENT, "event replay")
        if event.product_id != agreement.product_id:
            return None, Refusal(
                RefusalCode.CROSS_TENANT_ENTITLEMENT, "product/agreement mismatch"
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
            if (
                current.agreement_id != event.agreement_id
                or current.tenant_id != event.tenant_id
            ):
                return None, Refusal(
                    RefusalCode.CROSS_TENANT_ENTITLEMENT,
                    "entitlement cannot move agreement/tenant",
                )
            if event.revision <= current.revision:
                return None, Refusal(
                    RefusalCode.DUPLICATE_OR_STALE_EVENT, "stale revision"
                )
            target = _TRANSITIONS[current.state].get(event.kind)
            if target is None:
                return None, Refusal(
                    RefusalCode.ILLEGAL_LIFECYCLE_TRANSITION,
                    f"{current.state} cannot apply {event.kind}",
                )

        candidate = Entitlement(
            event.entitlement_id,
            event.agreement_id,
            event.tenant_id,
            event.product_id,
            target,
            event.quantity,
            event.revision,
            event.event_id,
            event.capabilities,
            event.support_tier,
        )
        receipt = self._brce(
            "entitlement.apply-event",
            event.entitlement_id,
            grant,
            {
                "state": target,
                "revision": event.revision,
                "quantity": event.quantity,
                "capabilities": sorted(event.capabilities),
            },
            f"event:{event.event_id}",
        )
        if isinstance(receipt, Refusal):
            return None, receipt
        self.entitlements[event.entitlement_id] = candidate
        self.processed_events.add(event.event_id)
        return candidate, receipt

    def observe_usage(self, observation: UsageObservation) -> CommerceReceipt:
        self.usage[observation.observation_id] = replace(observation, admitted=False)
        return self._store(
            _receipt(
                "usage.observe",
                observation.observation_id,
                "observation",
                {
                    "entitlement": observation.entitlement_id,
                    "dimension": observation.dimension_id,
                    "quantity": observation.quantity,
                },
                f"usage:{observation.observation_id}",
            )
        )

    def admit_usage(
        self, observation_id: str
    ) -> tuple[UsageObservation | None, CommerceReceipt | Refusal]:
        observation = self.usage[observation_id]
        entitlement = self.entitlements.get(observation.entitlement_id)
        if entitlement is None or entitlement.state is not EntitlementState.ACTIVE:
            return None, Refusal(
                RefusalCode.USAGE_WITHOUT_ACTIVE_ENTITLEMENT, "entitlement not active"
            )
        if entitlement.tenant_id != observation.tenant_id:
            return None, Refusal(
                RefusalCode.CROSS_TENANT_ENTITLEMENT, "usage tenant mismatch"
            )
        agreement = self.agreements[entitlement.agreement_id]
        if observation.dimension_id not in agreement.pricing_by_id:
            return None, Refusal(
                RefusalCode.PRICING_DIMENSION_MISMATCH, "dimension not priced"
            )
        admitted = replace(observation, admitted=True)
        self.usage[observation_id] = admitted
        receipt = self._store(
            _receipt(
                "usage.admit",
                observation_id,
                "commerce-kernel",
                {"admitted": True, "entitlement": observation.entitlement_id},
                f"usage-admit:{observation_id}",
            )
        )
        return admitted, receipt

    def construct_meter_intent(
        self, *, intent_id: str, observation_ids: Sequence[str]
    ) -> tuple[MeterIntent | None, CommerceReceipt | Refusal]:
        observations = [self.usage[item] for item in observation_ids]
        if not observations or any(not item.admitted for item in observations):
            return None, Refusal(
                RefusalCode.METER_WITHOUT_ADMITTED_USAGE, "all usage must be admitted"
            )
        entitlements = {item.entitlement_id for item in observations}
        dimensions = {item.dimension_id for item in observations}
        if len(entitlements) != 1 or len(dimensions) != 1:
            return None, Refusal(
                RefusalCode.METER_WITHOUT_ADMITTED_USAGE,
                "intent must bind one entitlement/dimension",
            )
        entitlement_id = next(iter(entitlements))
        dimension_id = next(iter(dimensions))
        entitlement = self.entitlements[entitlement_id]
        agreement = self.agreements[entitlement.agreement_id]
        price = agreement.pricing_by_id.get(dimension_id)
        if price is None:
            return None, Refusal(
                RefusalCode.PRICING_DIMENSION_MISMATCH, "dimension not priced"
            )
        quantity = sum(item.quantity for item in observations)
        amount = quantity * price.unit_price_micros
        receipt = self._store(
            _receipt(
                "meter.construct",
                intent_id,
                "commerce-kernel",
                {
                    "agreement": agreement.agreement_id,
                    "entitlement": entitlement_id,
                    "dimension": dimension_id,
                    "quantity": quantity,
                    "amount": amount,
                    "observations": sorted(observation_ids),
                },
                f"meter:{intent_id}",
            )
        )
        intent = MeterIntent(
            intent_id,
            agreement.agreement_id,
            entitlement_id,
            dimension_id,
            quantity,
            tuple(sorted(observation_ids)),
            amount,
            receipt.receipt_id,
        )
        self.meter_intents[intent_id] = intent
        return intent, receipt

    def admit_external_acceptance(
        self, acceptance: ExternalAcceptance
    ) -> tuple[ExternalAcceptance | None, CommerceReceipt | Refusal]:
        if (
            not acceptance.observed
            or not acceptance.evidence_ref
            or acceptance.evidence_origin is not EvidenceOrigin.LIVE_EXTERNAL
        ):
            return None, Refusal(
                RefusalCode.PROVIDER_ACCEPTANCE_NOT_OBSERVED,
                "provider acceptance requires observed LIVE_EXTERNAL evidence",
            )
        if acceptance.intent_id not in self.meter_intents:
            return None, Refusal(
                RefusalCode.METER_WITHOUT_ADMITTED_USAGE, "unknown meter intent"
            )
        self.acceptances[acceptance.acceptance_id] = acceptance
        receipt = self._store(
            _receipt(
                "provider.acceptance.admit",
                acceptance.acceptance_id,
                acceptance.provider,
                {
                    "intent": acceptance.intent_id,
                    "quantity": acceptance.accepted_quantity,
                    "evidence": acceptance.evidence_ref,
                },
                f"acceptance:{acceptance.acceptance_id}",
            )
        )
        return acceptance, receipt

    def reconcile(
        self, *, settlement_id: str, acceptance_id: str
    ) -> tuple[Settlement | None, CommerceReceipt | Refusal]:
        acceptance = self.acceptances.get(acceptance_id)
        if acceptance is None:
            return None, Refusal(
                RefusalCode.SETTLEMENT_WITHOUT_PROVIDER_ACCEPTANCE,
                "acceptance is not admitted",
            )
        intent = self.meter_intents[acceptance.intent_id]
        if acceptance.accepted_quantity != intent.quantity:
            return None, Refusal(
                RefusalCode.SETTLEMENT_WITHOUT_PROVIDER_ACCEPTANCE,
                "accepted quantity differs from meter intent",
            )
        receipt = self._store(
            _receipt(
                "settlement.reconcile",
                settlement_id,
                "commerce-kernel",
                {
                    "intent": intent.intent_id,
                    "acceptance": acceptance_id,
                    "amount": intent.amount_micros,
                },
                f"settlement:{settlement_id}",
            )
        )
        settlement = Settlement(
            settlement_id,
            intent.intent_id,
            acceptance_id,
            intent.amount_micros,
            receipt.receipt_id,
        )
        self.settlements[settlement_id] = settlement
        return settlement, receipt

    def admit_external_blocker_evidence(
        self,
        blocker: ExternalBlocker,
        evidence_ref: str,
        *,
        origin: EvidenceOrigin = EvidenceOrigin.FIXTURE,
    ) -> CommerceReceipt | Refusal:
        if not evidence_ref or origin is not EvidenceOrigin.LIVE_EXTERNAL:
            return Refusal(
                RefusalCode.PROVIDER_ACCEPTANCE_NOT_OBSERVED,
                f"{blocker} requires observed LIVE_EXTERNAL evidence",
            )
        self.external_evidence[blocker] = (evidence_ref, origin)
        return self._store(
            _receipt(
                "external-evidence.admit",
                blocker,
                "external",
                {"evidence": evidence_ref, "origin": origin},
                f"external:{blocker}:{evidence_ref}",
            )
        )

    def assert_identity_preservation(self) -> Refusal | None:
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
        finding = self.assert_identity_preservation()
        findings = (str(finding.code),) if finding else ()
        active = any(
            item.state is EntitlementState.ACTIVE for item in self.entitlements.values()
        )
        internal_executed = bool(
            self.agreements
            and active
            and any(item.admitted for item in self.usage.values())
            and self.meter_intents
            and self.receipts
        )
        internal = (
            Standing.ALIVE
            if internal_executed and packaging.complete and not findings
            else Standing.PARTIAL_ALIVE
        )
        missing_external = tuple(
            item for item in required_external if item not in self.external_evidence
        )
        external = Standing.ALIVE if not missing_external else Standing.BLOCKED
        return ReadinessReport(
            internal,
            external,
            packaging.missing,
            missing_external,
            findings,
        )


def capability_digest() -> str:
    """Stable class-closure digest for the ggen-marketplace projection."""
    return _digest(
        [
            {
                "id": item.capability_id,
                "operation": item.operation_kind,
                "reversible": item.reversible,
                "external": item.external_authority_required,
                "receipt": item.receipt_required,
                "description": item.description,
            }
            for item in CAPABILITIES
        ]
    )
