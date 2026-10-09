"""Capability cards from runtime surfaces: validity, real extraction, determinism.

Chicago-style: the tests import the real surfaces, run the real generator,
and assert on real state (the committed card files and the live FastAPI
route table / FastMCP tool registry / FastStream AST operations). No mocks.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).parent.parent
sys_path_prepended = str(_REPO_ROOT / "src")
import sys  # noqa: E402

if sys_path_prepended not in sys.path:
    sys.path.insert(0, sys_path_prepended)


from gymact.surfaces.fastapi import create_app  # noqa: E402
from gymact.surfaces.fastmcp import create_mcp  # noqa: E402
from gymact.surfaces.faststream import dispatch_stream_command  # noqa: E402

CARDS_DIR = _REPO_ROOT / "priv" / "cards"

_DOCS_ROUTES = {
    "/openapi.json",
    "/docs",
    "/redoc",
    "/docs/oauth2-redirect",
    "/.well-known/agent-card.json",
}


def _card(card_id: str) -> dict:
    path = CARDS_DIR / f"{card_id}.json"
    assert path.is_file(), f"missing committed card: {path}"
    return json.loads(path.read_text())


def test_http_card_routes_match_real_app_route_table() -> None:
    card = _card("gymact.http")
    app = create_app()
    real = sorted(
        f"{method} {route.path}"
        for route in app.routes
        if getattr(route, "methods", None)
        for method in route.methods - {"HEAD", "OPTIONS"}
        if route.path not in _DOCS_ROUTES
    )
    card_skills = sorted(skill["name"] for skill in card["skills"])
    assert card_skills == real
    assert len(card_skills) == len(real) == 18


def test_mcp_card_matches_real_tool_registry() -> None:
    card = _card("gymact.mcp")
    mcp = create_mcp()
    real_tools = sorted(tool.name for tool in asyncio.run(mcp.list_tools()))
    card_skills = sorted(skill["name"] for skill in card["skills"])
    assert card_skills == real_tools
    assert len(real_tools) == 10


@pytest.mark.asyncio
async def test_stream_card_operations_really_dispatch() -> None:
    card = _card("gymact.stream")
    from gymact.providers import MemoryProvider
    from gymact.runtime import ProductionGymAct

    service = ProductionGymAct()
    service.register_provider(MemoryProvider())
    ops = {skill["name"] for skill in card["skills"]}

    # A read operation really dispatches through the real dispatcher.
    result = await dispatch_stream_command(service, {"operation": "discover"})
    assert "discover" in ops
    assert result["operation"] == "discover"

    # An operation absent from the card must genuinely be unsupported.
    with pytest.raises(ValueError, match="unsupported stream operation"):
        await dispatch_stream_command(service, {"operation": "not_a_real_operation"})


def test_sa2a_transport_card_functions_exist_and_refuse() -> None:
    from gymact import sa2a_transport

    card = _card("gymact.sa2a-transport")
    names = {skill["name"] for skill in card["skills"]}
    assert names == {"a2a_task_to_envelope", "envelope_to_artifact"}
    assert callable(sa2a_transport.a2a_task_to_envelope)
    assert callable(sa2a_transport.envelope_to_artifact)

    # Real refusal: a malformed task yields a typed task.failed state.
    failed = sa2a_transport.a2a_task_to_envelope({})
    assert failed["status"]["state"] == "failed"
    description = card["description"]
    assert "SA2A_EXACT_SUBJECT_MISMATCH" in description
    assert "_authority_decision" in description


def test_all_cards_carry_authority_law_and_v10_protocol() -> None:
    for card_id in ("gymact.http", "gymact.mcp", "gymact.stream", "gymact.sa2a-transport"):
        card = _card(card_id)
        assert card["protocolVersion"] == "1.0"
        assert "_authority_decision" in card["description"]
        assert "admit_envelope" in card["description"]
        assert card["skills"], card_id


def test_well_known_route_serves_published_card_bytes() -> None:
    """GET /.well-known/agent-card.json -> 200 with the exact published bytes."""
    from fastapi.testclient import TestClient

    from gymact.surfaces.fastapi import AgentCardNotConfigured

    committed = (CARDS_DIR / "gymact.http.json").read_bytes()
    app = create_app()
    client = TestClient(app)

    response = client.get("/.well-known/agent-card.json")
    assert response.status_code == 200
    assert response.content == committed
    served = response.json()
    assert "supportedInterfaces" in served
    assert served["id"] == "gymact.http"
    assert "etag" in {k.lower() for k in response.headers}

    # Conditional revalidation against the ETag really 304s.
    revalidate = client.get(
        "/.well-known/agent-card.json",
        headers={"if-none-match": response.headers["etag"]},
    )
    assert revalidate.status_code == 304

    # Card selection is per instance; a configured-but-missing card is a
    # typed refusal at app creation, never a silent 404 at request time.
    with pytest.raises(AgentCardNotConfigured, match="AGENT_CARD_NOT_CONFIGURED"):
        create_app(card_id="gymact.does-not-exist")


def test_regeneration_is_byte_identical_to_committed_cards(tmp_path: Path) -> None:
    """Determinism court: a fresh run must reproduce every committed byte."""
    from scripts.gen_agent_cards import write_cards

    written = write_cards(tmp_path)
    assert len(written) == 4
    for path in written:
        committed = (CARDS_DIR / path.name).read_bytes()
        assert path.read_bytes() == committed, f"card drift: {path.name}"
