"""First-class GymAct provider for the provider-neutral Post-AGI DfCM commerce world.

This adapter deliberately exposes the complete 32-capability commerce class closure
without embedding any AWS, Microsoft, Google Cloud, Stripe, CRM, banking, tax, KYC,
or marketplace SDK. External authority edges are represented and refused; they are
never simulated into success.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import fields, is_dataclass
from enum import Enum
from typing import Any, Mapping
from uuid import uuid4

from gymact.models import Capability as GymCapability
from gymact.models import Consequence

from .commerce_dfcm import (
    CAPABILITIES,
    BillingAuthority,
    BrokerGrant,
    CommercialAgreement,
    EntitlementEvent,
    EventKind,
    EvidenceOrigin,
    ExternalAcceptance,
    OperationKind,
    PackagingEvidence,
    PricingDimension,
    Refusal,
    RefusalCode,
    UsageObservation,
    _receipt,
)
from .commerce_dfcm_enterprise import EnterpriseCommerceWorld


COMMERCE_DFCM_CAPABILITIES: tuple[GymCapability, ...] = tuple(
    GymCapability(
        iri=f"urn:gymact:commerce-dfcm:capability:{item.capability_id}",
        title=(
            f"{item.description} "
            f"DfCM={item.operation_kind.value}; reversible={str(item.reversible).lower()}; "
            f"external_authority_required={str(item.external_authority_required).lower()}."
        ),
        consequence=(
            Consequence.READ if item.operation_kind is OperationKind.SELECT else Consequence.DO
        ),
        binding=item.capability_id,
    )
    for item in CAPABILITIES
)

_CAPABILITY_BY_BINDING = {item.binding: item for item in COMMERCE_DFCM_CAPABILITIES}
_EXTERNAL_DO_BINDINGS = frozenset(
    item.capability_id
    for item in CAPABILITIES
    if item.operation_kind is OperationKind.DO and item.external_authority_required
)
_PACKAGING_BINDINGS = frozenset(
    {
        "packaging.helm",
        "packaging.k8s-stable-api",
        "supply-chain.sbom",
        "supply-chain.vulnerability-scan",
        "supply-chain.provenance",
        "artifact.portable-registry",
    }
)


def _jsonify(value: Any) -> Any:
    if is_dataclass(value):
        return {field.name: _jsonify(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Mapping):
        return {str(key): _jsonify(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_jsonify(item) for item in value]
    return value


def _require_mapping(value: Any, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{name} must be an object")
    return value


def _pricing(value: Any) -> tuple[PricingDimension, ...]:
    if not isinstance(value, list):
        raise TypeError("pricing must be a list")
    return tuple(
        PricingDimension(
            dimension_id=str(_require_mapping(item, "pricing item")["dimension_id"]),
            unit=str(_require_mapping(item, "pricing item")["unit"]),
            unit_price_micros=int(_require_mapping(item, "pricing item")["unit_price_micros"]),
        )
        for item in value
    )


def _agreement(payload: Mapping[str, Any]) -> CommercialAgreement:
    body = _require_mapping(payload.get("agreement", payload), "agreement")
    return CommercialAgreement(
        agreement_id=str(body["agreement_id"]),
        legal_entity_id=str(body["legal_entity_id"]),
        account_id=str(body["account_id"]),
        product_id=str(body["product_id"]),
        offer_id=str(body["offer_id"]),
        billing_authority=BillingAuthority(str(body["billing_authority"])),
        pricing=_pricing(body.get("pricing", [])),
        effective_at=str(body["effective_at"]),
        expires_at=str(body["expires_at"]) if body.get("expires_at") is not None else None,
        external_source=(
            str(body["external_source"]) if body.get("external_source") is not None else None
        ),
        negotiated_terms_ref=(
            str(body["negotiated_terms_ref"])
            if body.get("negotiated_terms_ref") is not None
            else None
        ),
    )


def _grant(payload: Mapping[str, Any]) -> BrokerGrant | None:
    raw = payload.get("grant")
    if raw is None:
        return None
    body = _require_mapping(raw, "grant")
    return BrokerGrant(
        grant_id=str(body["grant_id"]),
        authority=str(body["authority"]),
        subject_id=str(body["subject_id"]),
        allowed_operation=str(body["allowed_operation"]),
        evidence_ref=str(body["evidence_ref"]),
    )


def _event(payload: Mapping[str, Any]) -> EntitlementEvent:
    body = _require_mapping(payload.get("event", payload), "event")
    capabilities = body.get("capabilities", [])
    if not isinstance(capabilities, (list, tuple, set, frozenset)):
        raise TypeError("event.capabilities must be an array")
    return EntitlementEvent(
        event_id=str(body["event_id"]),
        source=str(body["source"]),
        kind=EventKind(str(body["kind"])),
        agreement_id=str(body["agreement_id"]),
        entitlement_id=str(body["entitlement_id"]),
        tenant_id=str(body["tenant_id"]),
        product_id=str(body["product_id"]),
        revision=int(body["revision"]),
        quantity=int(body.get("quantity", 1)),
        capabilities=frozenset(str(item) for item in capabilities),
        support_tier=(
            str(body["support_tier"]) if body.get("support_tier") is not None else None
        ),
    )


def _usage(payload: Mapping[str, Any]) -> UsageObservation:
    body = _require_mapping(payload.get("observation", payload), "observation")
    return UsageObservation(
        observation_id=str(body["observation_id"]),
        entitlement_id=str(body["entitlement_id"]),
        tenant_id=str(body["tenant_id"]),
        dimension_id=str(body["dimension_id"]),
        quantity=int(body["quantity"]),
        observed_at=str(body["observed_at"]),
    )


def _acceptance(payload: Mapping[str, Any]) -> ExternalAcceptance:
    body = _require_mapping(payload.get("acceptance", payload), "acceptance")
    return ExternalAcceptance(
        acceptance_id=str(body["acceptance_id"]),
        intent_id=str(body["intent_id"]),
        provider=str(body["provider"]),
        observed=bool(body.get("observed", False)),
        evidence_ref=str(body.get("evidence_ref", "")),
        accepted_quantity=int(body["accepted_quantity"]),
        evidence_origin=EvidenceOrigin(str(body.get("evidence_origin", "FIXTURE"))),
    )


def _packaging(payload: Mapping[str, Any]) -> PackagingEvidence:
    body = _require_mapping(payload.get("packaging", payload), "packaging")
    return PackagingEvidence(
        helm_chart=bool(body.get("helm_chart", False)),
        stable_kubernetes_apis=bool(body.get("stable_kubernetes_apis", False)),
        sbom=bool(body.get("sbom", False)),
        vulnerability_scan=bool(body.get("vulnerability_scan", False)),
        signed_provenance=bool(body.get("signed_provenance", False)),
        portable_registry_artifact=bool(body.get("portable_registry_artifact", False)),
    )


def _encode_outcome(value: Any) -> dict[str, Any]:
    if isinstance(value, Refusal):
        return {"standing": "REFUSED", "refusal": _jsonify(value)}
    if isinstance(value, tuple) and len(value) == 2:
        subject, evidence = value
        if isinstance(evidence, Refusal):
            return {
                "standing": "REFUSED",
                "subject": _jsonify(subject),
                "refusal": _jsonify(evidence),
            }
        return {
            "standing": "ALIVE",
            "subject": _jsonify(subject),
            "evidence": _jsonify(evidence),
        }
    return {"standing": "ALIVE", "subject": _jsonify(value)}


class CommerceDfcmEnvironment:
    """Bounded executable commerce world with a hard external-authority ceiling."""

    def __init__(self, *, requires_authority: bool = True) -> None:
        self.environment_id = f"urn:gymact:commerce-dfcm:environment:{uuid4().hex}"
        self.requires_authority = requires_authority
        self.world = EnterpriseCommerceWorld()
        self._checkpoints: dict[str, EnterpriseCommerceWorld] = {}
        self._closed = False

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError("environment is torn down")

    def capabilities(self) -> tuple[GymCapability, ...]:
        self._ensure_open()
        return COMMERCE_DFCM_CAPABILITIES

    def _state(self) -> dict[str, Any]:
        return {
            "agreement_ids": sorted(self.world.agreements),
            "entitlement_ids": sorted(self.world.entitlements),
            "usage_observation_ids": sorted(self.world.usage),
            "meter_intent_ids": sorted(self.world.meter_intents),
            "acceptance_ids": sorted(self.world.acceptances),
            "settlement_ids": sorted(self.world.settlements),
            "identity_binding_ids": sorted(self.world.identity_bindings),
            "adjustment_ids": sorted(self.world.adjustments),
            "support_projection_ids": sorted(self.world.support_projections),
            "receipt_count": len(self.world.receipts),
            "external_evidence": sorted(item.value for item in self.world.external_evidence),
            "packaging_admitted": self.world.packaging_admission is not None,
        }

    async def observe(self) -> dict[str, Any]:
        self._ensure_open()
        return self._state()

    async def actuate(
        self, capability: GymCapability, payload: dict[str, Any]
    ) -> dict[str, Any]:
        self._ensure_open()
        if capability.binding not in _CAPABILITY_BY_BINDING:
            raise ValueError(f"unsupported commerce-dfcm binding: {capability.binding}")
        before = self._state()
        binding = capability.binding

        if binding in _EXTERNAL_DO_BINDINGS:
            outcome: Any = Refusal(
                RefusalCode.EXTERNAL_DO_WITHOUT_AUTHORITY,
                f"{binding} is an external-authority edge and is not actuated by GymAct",
            )
        elif binding in {"agreement.admit", "billing-authority.fence"}:
            outcome = self.world.admit_agreement(_agreement(payload))
        elif binding in {
            "entitlement.apply-event",
            "entitlement.lifecycle",
            "replay.idempotent",
        }:
            event = _event(payload)
            source = str(payload.get("source", event.source))
            outcome = self.world.apply_entitlement_event(source, event, grant=_grant(payload))
        elif binding == "entitlement.concurrent":
            refusal = self.world.assert_identity_preservation()
            if refusal is not None:
                outcome = refusal
            else:
                receipt = self.world._store(
                    _receipt(
                        "entitlement.concurrent",
                        self.environment_id,
                        "commerce-kernel",
                        {"preserved": True, "entitlements": sorted(self.world.entitlements)},
                        f"identity-preservation:{len(self.world.receipts)}",
                    )
                )
                outcome = ({"preserved": True}, receipt)
        elif binding == "identity.bind":
            outcome = self.world.bind_identity(
                binding_id=str(payload["binding_id"]),
                account_id=str(payload["account_id"]),
                tenant_id=str(payload["tenant_id"]),
                issuer=str(payload["issuer"]),
                subject=str(payload["subject"]),
            )
        elif binding == "usage.observe":
            observation = _usage(payload)
            receipt = self.world.observe_usage(observation)
            outcome = (self.world.usage[observation.observation_id], receipt)
        elif binding in {"usage.admit", "pricing.validate"}:
            outcome = self.world.admit_usage(str(payload["observation_id"]))
        elif binding == "meter.construct":
            observation_ids = payload.get("observation_ids")
            if not isinstance(observation_ids, list):
                raise TypeError("observation_ids must be a list")
            outcome = self.world.construct_meter_intent(
                intent_id=str(payload["intent_id"]),
                observation_ids=[str(item) for item in observation_ids],
            )
        elif binding == "provider.acceptance.admit":
            outcome = self.world.admit_external_acceptance(_acceptance(payload))
        elif binding == "settlement.reconcile":
            outcome = self.world.reconcile(
                settlement_id=str(payload["settlement_id"]),
                acceptance_id=str(payload["acceptance_id"]),
            )
        elif binding == "agreement.amend":
            outcome = self.world.amend_agreement(
                str(payload["agreement_id"]),
                pricing=_pricing(payload.get("pricing", [])),
                offer_id=str(payload["offer_id"]),
                grant=_grant(payload),
            )
        elif binding == "agreement.renew":
            outcome = self.world.renew_agreement(
                str(payload["agreement_id"]),
                expires_at=str(payload["expires_at"]),
                grant=_grant(payload),
            )
        elif binding == "agreement.cancel":
            outcome = self.world.cancel_agreement(
                str(payload["agreement_id"]), grant=_grant(payload)
            )
        elif binding == "credit.construct":
            outcome = self.world.construct_credit(
                adjustment_id=str(payload["adjustment_id"]),
                agreement_id=str(payload["agreement_id"]),
                amount_micros=int(payload["amount_micros"]),
                reason=str(payload["reason"]),
            )
        elif binding == "refund.construct":
            outcome = self.world.construct_refund(
                adjustment_id=str(payload["adjustment_id"]),
                agreement_id=str(payload["agreement_id"]),
                amount_micros=int(payload["amount_micros"]),
                reason=str(payload["reason"]),
            )
        elif binding == "support.entitle":
            outcome = self.world.project_support(str(payload["entitlement_id"]))
        elif binding in _PACKAGING_BINDINGS:
            outcome = self.world.admit_packaging(_packaging(payload))
        else:
            raise AssertionError(f"capability catalog/dispatcher drift: {binding}")

        return {
            "before": before,
            "after": self._state(),
            "capability": capability.iri,
            "binding": binding,
            **_encode_outcome(outcome),
        }

    async def verify(self, expected: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
        self._ensure_open()
        observed = self._state()
        return all(observed.get(key) == value for key, value in expected.items()), observed

    async def checkpoint(self) -> dict[str, Any]:
        self._ensure_open()
        checkpoint_id = uuid4().hex
        self._checkpoints[checkpoint_id] = deepcopy(self.world)
        return {"checkpoint_id": checkpoint_id}

    async def restore(self, checkpoint: dict[str, Any]) -> None:
        self._ensure_open()
        checkpoint_id = checkpoint.get("checkpoint_id")
        if not isinstance(checkpoint_id, str) or checkpoint_id not in self._checkpoints:
            raise ValueError("unknown commerce-dfcm checkpoint")
        self.world = deepcopy(self._checkpoints[checkpoint_id])

    async def teardown(self) -> None:
        self._closed = True
        self._checkpoints.clear()


class CommerceDfcmProvider:
    """Materialize isolated, provider-neutral commerce worlds."""

    name = "commerce-dfcm"
    materialization_requires_authority = False

    async def materialize(
        self, *, scenario: str | None, config: dict[str, Any]
    ) -> CommerceDfcmEnvironment:
        if scenario not in (None, "provider-neutral", "fortune-5-commerce"):
            raise ValueError(f"unsupported commerce-dfcm scenario: {scenario}")
        requires_authority = config.get("requires_authority", True)
        if not isinstance(requires_authority, bool):
            raise TypeError("config.requires_authority must be a boolean")
        return CommerceDfcmEnvironment(requires_authority=requires_authority)
