"""Deterministic enterprise-company simulation for GymAct.

This provider models a consulting/staffing/delivery company as an economic world:
leads become opportunities, opportunities become engagements, people are hired and
staffed, milestones create billable value, invoices are issued/collected, and clients
renew or churn. It is a simulation provider: no external CRM, ERP, social network,
payment rail, or identity system is contacted.

The world deliberately separates internal behavioral-fidelity tests from public identity
presentation. Synthetic personas may be rendered human-plausibly inside the gym, but any
external/public surface is required to carry ``synthetic_disclosure=True``. This lets a
benchmark test realism without silently manufacturing real-person identity claims.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any
from uuid import uuid4

from gymact.models import Capability, Consequence


ENTERPRISE_COMPANY_CAPABILITIES: tuple[Capability, ...] = (
    Capability(
        iri="urn:gymact:enterprise-company:capability:create_lead",
        title="Create a simulated enterprise lead",
        consequence=Consequence.DO,
        binding="create_lead",
    ),
    Capability(
        iri="urn:gymact:enterprise-company:capability:qualify_lead",
        title="Qualify a simulated lead into an opportunity",
        consequence=Consequence.DO,
        binding="qualify_lead",
    ),
    Capability(
        iri="urn:gymact:enterprise-company:capability:close_engagement",
        title="Close a simulated opportunity into a revenue engagement",
        consequence=Consequence.DO,
        binding="close_engagement",
    ),
    Capability(
        iri="urn:gymact:enterprise-company:capability:hire_persona",
        title="Hire a synthetic worker persona into the simulated company",
        consequence=Consequence.DO,
        binding="hire_persona",
    ),
    Capability(
        iri="urn:gymact:enterprise-company:capability:staff_engagement",
        title="Staff a synthetic worker persona onto a simulated engagement",
        consequence=Consequence.DO,
        binding="staff_engagement",
    ),
    Capability(
        iri="urn:gymact:enterprise-company:capability:deliver_milestone",
        title="Deliver a milestone and create simulated billable value",
        consequence=Consequence.DO,
        binding="deliver_milestone",
    ),
    Capability(
        iri="urn:gymact:enterprise-company:capability:invoice",
        title="Issue a simulated invoice for accrued billable value",
        consequence=Consequence.DO,
        binding="invoice",
    ),
    Capability(
        iri="urn:gymact:enterprise-company:capability:collect",
        title="Collect a simulated invoice and recognize cash",
        consequence=Consequence.DO,
        binding="collect",
    ),
    Capability(
        iri="urn:gymact:enterprise-company:capability:renew",
        title="Renew a simulated engagement",
        consequence=Consequence.DO,
        binding="renew",
    ),
    Capability(
        iri="urn:gymact:enterprise-company:capability:churn",
        title="Churn a simulated engagement",
        consequence=Consequence.DO,
        binding="churn",
    ),
    Capability(
        iri="urn:gymact:enterprise-company:capability:publish_profile",
        title="Render a synthetic professional profile; external surfaces require disclosure",
        consequence=Consequence.DO,
        binding="publish_profile",
    ),
    Capability(
        iri="urn:gymact:enterprise-company:capability:score_company",
        title="Read company operating and economic KPIs",
        consequence=Consequence.READ,
        binding="score_company",
    ),
)


class EnterpriseCompanyEnvironment:
    """One bounded deterministic company world."""

    def __init__(self, *, company_name: str, requires_authority: bool = True) -> None:
        self.environment_id = f"urn:gymact:enterprise-company:environment:{uuid4().hex}"
        self.requires_authority = requires_authority
        self._closed = False
        self._state: dict[str, Any] = {
            "company_name": company_name,
            "leads": {},
            "opportunities": {},
            "engagements": {},
            "people": {},
            "profiles": {},
            "invoices": {},
            "cash_collected": 0.0,
            "recognized_revenue": 0.0,
            "delivery_cost": 0.0,
            "next_id": 1,
        }

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError("environment is torn down")

    def capabilities(self) -> tuple[Capability, ...]:
        self._ensure_open()
        return ENTERPRISE_COMPANY_CAPABILITIES

    def _new_id(self, prefix: str) -> str:
        value = int(self._state["next_id"])
        self._state["next_id"] = value + 1
        return f"{prefix}-{value:05d}"

    def _kpis(self) -> dict[str, Any]:
        active = [e for e in self._state["engagements"].values() if e["status"] == "active"]
        staffed = sum(len(e["staff"]) for e in active)
        headcount = len(self._state["people"])
        revenue = float(self._state["recognized_revenue"])
        cost = float(self._state["delivery_cost"])
        return {
            "lead_count": len(self._state["leads"]),
            "opportunity_count": len(self._state["opportunities"]),
            "active_engagements": len(active),
            "headcount": headcount,
            "staffed_assignments": staffed,
            "utilization": 0.0 if headcount == 0 else staffed / headcount,
            "recognized_revenue": revenue,
            "cash_collected": float(self._state["cash_collected"]),
            "delivery_cost": cost,
            "gross_margin": 0.0 if revenue == 0 else (revenue - cost) / revenue,
        }

    async def observe(self) -> dict[str, Any]:
        self._ensure_open()
        return {"company_name": self._state["company_name"], "kpis": self._kpis()}

    async def actuate(self, capability: Capability, payload: dict[str, Any]) -> dict[str, Any]:
        self._ensure_open()
        before = self._kpis()
        binding = capability.binding

        if binding == "create_lead":
            client = _required_str(payload, "client")
            region = _required_str(payload, "region")
            service = _required_str(payload, "service")
            lead_id = self._new_id("lead")
            self._state["leads"][lead_id] = {
                "client": client,
                "region": region,
                "service": service,
                "status": "new",
            }
            result: Any = {"lead_id": lead_id}

        elif binding == "qualify_lead":
            lead_id = _required_str(payload, "lead_id")
            lead = self._state["leads"].get(lead_id)
            if lead is None:
                raise ValueError("unknown lead_id")
            annual_value = _positive_number(payload, "annual_value")
            probability = float(payload.get("probability", 0.5))
            if not 0.0 <= probability <= 1.0:
                raise ValueError("probability must be between 0 and 1")
            opportunity_id = self._new_id("opp")
            lead["status"] = "qualified"
            self._state["opportunities"][opportunity_id] = {
                "lead_id": lead_id,
                "client": lead["client"],
                "service": lead["service"],
                "region": lead["region"],
                "annual_value": annual_value,
                "probability": probability,
                "status": "open",
            }
            result = {"opportunity_id": opportunity_id}

        elif binding == "close_engagement":
            opportunity_id = _required_str(payload, "opportunity_id")
            opp = self._state["opportunities"].get(opportunity_id)
            if opp is None:
                raise ValueError("unknown opportunity_id")
            if opp["status"] != "open":
                raise ValueError("opportunity is not open")
            engagement_id = self._new_id("eng")
            opp["status"] = "won"
            self._state["engagements"][engagement_id] = {
                "opportunity_id": opportunity_id,
                "client": opp["client"],
                "service": opp["service"],
                "region": opp["region"],
                "annual_value": opp["annual_value"],
                "status": "active",
                "staff": [],
                "unbilled": 0.0,
                "renewals": 0,
            }
            result = {"engagement_id": engagement_id}

        elif binding == "hire_persona":
            name = _required_str(payload, "name")
            role = _required_str(payload, "role")
            region = _required_str(payload, "region")
            hourly_cost = _positive_number(payload, "hourly_cost")
            person_id = self._new_id("person")
            self._state["people"][person_id] = {
                "name": name,
                "role": role,
                "region": region,
                "hourly_cost": hourly_cost,
                "synthetic": True,
            }
            result = {"person_id": person_id}

        elif binding == "staff_engagement":
            engagement_id = _required_str(payload, "engagement_id")
            person_id = _required_str(payload, "person_id")
            engagement = self._state["engagements"].get(engagement_id)
            person = self._state["people"].get(person_id)
            if engagement is None or person is None:
                raise ValueError("unknown engagement_id or person_id")
            if engagement["status"] != "active":
                raise ValueError("engagement is not active")
            if person_id not in engagement["staff"]:
                engagement["staff"].append(person_id)
            result = {"staffed": True}

        elif binding == "deliver_milestone":
            engagement_id = _required_str(payload, "engagement_id")
            engagement = self._state["engagements"].get(engagement_id)
            if engagement is None or engagement["status"] != "active":
                raise ValueError("engagement is not active")
            billable = _positive_number(payload, "billable")
            hours = _positive_number(payload, "hours")
            if not engagement["staff"]:
                raise ValueError("engagement has no staff")
            per_person_hours = hours / len(engagement["staff"])
            cost = sum(
                self._state["people"][pid]["hourly_cost"] * per_person_hours
                for pid in engagement["staff"]
            )
            engagement["unbilled"] += billable
            self._state["recognized_revenue"] += billable
            self._state["delivery_cost"] += cost
            result = {"billable": billable, "delivery_cost": cost}

        elif binding == "invoice":
            engagement_id = _required_str(payload, "engagement_id")
            engagement = self._state["engagements"].get(engagement_id)
            if engagement is None:
                raise ValueError("unknown engagement_id")
            amount = float(engagement["unbilled"])
            if amount <= 0:
                raise ValueError("nothing to invoice")
            invoice_id = self._new_id("inv")
            engagement["unbilled"] = 0.0
            self._state["invoices"][invoice_id] = {
                "engagement_id": engagement_id,
                "amount": amount,
                "status": "open",
            }
            result = {"invoice_id": invoice_id, "amount": amount}

        elif binding == "collect":
            invoice_id = _required_str(payload, "invoice_id")
            invoice = self._state["invoices"].get(invoice_id)
            if invoice is None or invoice["status"] != "open":
                raise ValueError("invoice is not open")
            invoice["status"] = "paid"
            self._state["cash_collected"] += invoice["amount"]
            result = {"collected": invoice["amount"]}

        elif binding == "renew":
            engagement_id = _required_str(payload, "engagement_id")
            engagement = self._state["engagements"].get(engagement_id)
            if engagement is None or engagement["status"] != "active":
                raise ValueError("engagement is not active")
            uplift = float(payload.get("uplift", 0.0))
            if uplift < -1.0:
                raise ValueError("uplift cannot reduce annual value below zero")
            engagement["annual_value"] *= 1.0 + uplift
            engagement["renewals"] += 1
            result = {"annual_value": engagement["annual_value"], "renewals": engagement["renewals"]}

        elif binding == "churn":
            engagement_id = _required_str(payload, "engagement_id")
            engagement = self._state["engagements"].get(engagement_id)
            if engagement is None or engagement["status"] != "active":
                raise ValueError("engagement is not active")
            engagement["status"] = "churned"
            result = {"status": "churned"}

        elif binding == "publish_profile":
            person_id = _required_str(payload, "person_id")
            person = self._state["people"].get(person_id)
            if person is None:
                raise ValueError("unknown person_id")
            surface = _required_str(payload, "surface")
            synthetic_disclosure = bool(payload.get("synthetic_disclosure", False))
            if surface != "internal" and not synthetic_disclosure:
                raise ValueError("PUBLIC_SYNTHETIC_IDENTITY_REQUIRES_DISCLOSURE")
            profile_id = self._new_id("profile")
            profile = {
                "person_id": person_id,
                "surface": surface,
                "display_name": person["name"],
                "headline": payload.get("headline", person["role"]),
                "avatar_ref": payload.get("avatar_ref"),
                "synthetic_disclosure": synthetic_disclosure,
            }
            self._state["profiles"][profile_id] = profile
            result = {"profile_id": profile_id, "profile": profile}

        elif binding == "score_company":
            result = self._kpis()

        else:
            raise ValueError(f"unsupported enterprise-company binding: {binding}")

        return {
            "before": before,
            "after": self._kpis(),
            "capability": capability.iri,
            "result": result,
        }

    async def verify(self, expected: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
        self._ensure_open()
        observed = self._kpis()
        passed = all(observed.get(key) == value for key, value in expected.items())
        return passed, observed

    async def checkpoint(self) -> dict[str, Any]:
        self._ensure_open()
        return deepcopy(self._state)

    async def restore(self, checkpoint: dict[str, Any]) -> None:
        self._ensure_open()
        if checkpoint.get("company_name") != self._state["company_name"]:
            raise ValueError("checkpoint belongs to a different company world")
        self._state = deepcopy(checkpoint)

    async def teardown(self) -> None:
        self._closed = True


class EnterpriseCompanyProvider:
    """Materialize a deterministic enterprise-company simulation."""

    name = "enterprise-company"
    materialization_requires_authority = False

    async def materialize(
        self, *, scenario: str | None, config: dict[str, Any]
    ) -> EnterpriseCompanyEnvironment:
        company_name = config.get("company_name", "Synthetic Enterprise Consulting")
        if not isinstance(company_name, str) or not company_name.strip():
            raise TypeError("config.company_name must be a non-empty string")
        requires_authority = config.get("requires_authority", True)
        if not isinstance(requires_authority, bool):
            raise TypeError("config.requires_authority must be a boolean")
        return EnterpriseCompanyEnvironment(
            company_name=company_name.strip(), requires_authority=requires_authority
        )


def _required_str(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"payload.{key} must be a non-empty string")
    return value.strip()


def _positive_number(payload: dict[str, Any], key: str) -> float:
    value = payload.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"payload.{key} must be a positive number")
    number = float(value)
    if number <= 0:
        raise ValueError(f"payload.{key} must be a positive number")
    return number
