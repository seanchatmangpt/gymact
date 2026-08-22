from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from fastmcp.client import Client

from gymact.surfaces.fastapi import create_app
from gymact.surfaces.fastmcp import create_mcp

CAPABILITY = "urn:gymact:memory:capability:set"


def _candidate(episode_id: str) -> dict[str, object]:
    return {
        "episode_id": episode_id,
        "action_ref": "urn:action:set",
        "subject": {
            "semantic_id": "urn:subject:memory",
            "provider_ref": "urn:provider:memory",
        },
        "payload": {"key": "x", "value": 2},
        "admission_digest": "observation-1",
        "idempotency_key": "candidate-1",
    }


def test_default_rest_constructs_candidate_but_refuses_raw_do() -> None:
    # TestClient owns an AnyIO blocking portal and lifespan streams. Entering
    # its context is the ownership boundary: __exit__ closes those resources
    # before the next pytest item can collect them as delayed unraisables.
    with TestClient(create_app()) as client:
        created = client.post(
            "/episodes",
            json={
                "provider": "memory",
                "config": {"initial": {"x": 1}},
                "idempotency_key": "rest-prod-materialize",
            },
        ).json()
        episode_id = created["episode"]["episode_id"]
        candidate = client.post("/candidates", json=_candidate(episode_id))
        assert candidate.status_code == 200
        assert candidate.json()["prepared"]["episode_id"] == episode_id

        raw = client.post(
            f"/episodes/{episode_id}/actions",
            json={
                "episode_id": episode_id,
                "capability": CAPABILITY,
                "payload": {"key": "x", "value": 2},
                "idempotency_key": "rest-raw",
            },
        ).json()
        assert raw["standing"] == "REFUSED"
        assert raw["receipt"]["reason"] == "BRCE_EXECUTION_GRANT_REQUIRED"
        observed = client.get(f"/episodes/{episode_id}/observations/latest").json()
        assert observed["state"] == {"x": 1}


@pytest.mark.asyncio
async def test_default_mcp_constructs_candidate_but_refuses_raw_do() -> None:
    async with Client(create_mcp()) as client:
        created = await client.call_tool(
            "create_episode",
            {
                "provider": "memory",
                "config": {"initial": {"x": 1}},
                "idempotency_key": "mcp-prod-materialize",
            },
        )
        episode_id = created.data["episode"]["episode_id"]
        candidate = await client.call_tool(
            "act",
            {"candidate": _candidate(episode_id)},
        )
        assert candidate.data["mode"] == "CONSTRUCT"
        assert candidate.data["prepared"]["episode_id"] == episode_id

        raw = await client.call_tool(
            "act",
            {
                "episode_id": episode_id,
                "capability": CAPABILITY,
                "payload": {"key": "x", "value": 2},
                "idempotency_key": "mcp-raw",
            },
        )
        assert raw.data["standing"] == "REFUSED"
        assert raw.data["receipt"]["reason"] == "BRCE_EXECUTION_GRANT_REQUIRED"
        observed = await client.call_tool("observe", {"episode_id": episode_id})
        assert observed.data["state"] == {"x": 1}
