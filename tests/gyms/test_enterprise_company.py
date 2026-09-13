from __future__ import annotations

import asyncio

import pytest

from gymact.gyms.enterprise_company import (
    ENTERPRISE_COMPANY_CAPABILITIES,
    EnterpriseCompanyProvider,
)


CAP = {cap.binding: cap for cap in ENTERPRISE_COMPANY_CAPABILITIES}


def _act(env, binding: str, payload: dict):
    return asyncio.run(env.actuate(CAP[binding], payload))


def test_full_revenue_loop_produces_real_simulated_economic_state() -> None:
    env = asyncio.run(
        EnterpriseCompanyProvider().materialize(
            scenario="global-enterprise-consulting",
            config={"company_name": "Freedom Consulting Twin", "requires_authority": True},
        )
    )

    lead_id = _act(
        env,
        "create_lead",
        {"client": "Global Manufacturer", "region": "US", "service": "SAP + AI transformation"},
    )["result"]["lead_id"]
    opportunity_id = _act(
        env,
        "qualify_lead",
        {"lead_id": lead_id, "annual_value": 1_200_000, "probability": 0.7},
    )["result"]["opportunity_id"]
    engagement_id = _act(
        env, "close_engagement", {"opportunity_id": opportunity_id}
    )["result"]["engagement_id"]
    person_id = _act(
        env,
        "hire_persona",
        {
            "name": "Synthetic Principal FDE",
            "role": "Principal Forward Deployment Engineer",
            "region": "US",
            "hourly_cost": 100,
        },
    )["result"]["person_id"]
    _act(
        env,
        "staff_engagement",
        {"engagement_id": engagement_id, "person_id": person_id},
    )
    delivered = _act(
        env,
        "deliver_milestone",
        {"engagement_id": engagement_id, "billable": 50_000, "hours": 100},
    )
    invoice_id = _act(env, "invoice", {"engagement_id": engagement_id})["result"][
        "invoice_id"
    ]
    _act(env, "collect", {"invoice_id": invoice_id})

    assert delivered["result"]["delivery_cost"] == 10_000
    verified, observed = asyncio.run(
        env.verify(
            {
                "active_engagements": 1,
                "headcount": 1,
                "recognized_revenue": 50_000.0,
                "cash_collected": 50_000.0,
                "delivery_cost": 10_000.0,
                "gross_margin": 0.8,
            }
        )
    )
    assert verified
    assert observed["utilization"] == 1.0


def test_public_synthetic_profile_requires_disclosure() -> None:
    env = asyncio.run(
        EnterpriseCompanyProvider().materialize(scenario=None, config={})
    )
    person_id = _act(
        env,
        "hire_persona",
        {
            "name": "Synthetic Recruiter",
            "role": "Technical Recruiter",
            "region": "Europe",
            "hourly_cost": 60,
        },
    )["result"]["person_id"]

    with pytest.raises(ValueError, match="PUBLIC_SYNTHETIC_IDENTITY_REQUIRES_DISCLOSURE"):
        _act(
            env,
            "publish_profile",
            {
                "person_id": person_id,
                "surface": "linkedin",
                "headline": "AI Center of Excellence | Enterprise AI",
                "avatar_ref": "urn:synthetic-avatar:recruiter-001",
            },
        )

    profile = _act(
        env,
        "publish_profile",
        {
            "person_id": person_id,
            "surface": "linkedin",
            "headline": "AI Center of Excellence | Enterprise AI",
            "avatar_ref": "urn:synthetic-avatar:recruiter-001",
            "synthetic_disclosure": True,
        },
    )["result"]["profile"]
    assert profile["synthetic_disclosure"] is True
    assert profile["avatar_ref"] == "urn:synthetic-avatar:recruiter-001"


def test_checkpoint_restore_replays_company_state() -> None:
    env = asyncio.run(
        EnterpriseCompanyProvider().materialize(
            scenario=None, config={"company_name": "Replayable Company"}
        )
    )
    checkpoint = asyncio.run(env.checkpoint())
    _act(
        env,
        "create_lead",
        {"client": "Client A", "region": "APAC", "service": "Salesforce transformation"},
    )
    assert asyncio.run(env.observe())["kpis"]["lead_count"] == 1
    asyncio.run(env.restore(checkpoint))
    assert asyncio.run(env.observe())["kpis"]["lead_count"] == 0
