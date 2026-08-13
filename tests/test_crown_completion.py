from __future__ import annotations

from fastapi.testclient import TestClient
from typer.main import get_command

from gymact import (
    MemoryProvider,
    MemoryReceiptLedger,
    Operation,
    Receipt,
    Standing,
    build_contract,
)
from gymact.cli import app as cli_app
from gymact.replay import ReplayMode, replay_ledger
from gymact.runtime import GymAct
from gymact.surfaces.fastapi import create_app


def test_cli_exposes_complete_canonical_surface() -> None:
    commands = set(get_command(cli_app).commands)
    required = {
        "providers",
        "capabilities",
        "inspect",
        "prepare",
        "execute",
        "observe",
        "verify",
        "reconcile",
        "replay",
        "doctor",
        "benchmark",
        "errc-status",
    }
    assert required <= commands


def test_openapi_makes_dcm_selected_cut_the_canonical_production_do(request) -> None:
    runtime = GymAct()
    runtime.register_provider(MemoryProvider())
    client = TestClient(create_app(runtime))
    # See the matching comment in
    # `tests/test_core.py::test_fastapi_surface_executes_real_episode_and_contract_routes`
    # -- an unclosed `TestClient` leaks anyio memory streams, surfaced by
    # pytest's unraisable-exception plugin against a later, unrelated test.
    request.addfinalizer(client.close)
    schema = client.get("/openapi.json").json()
    paths = schema["paths"]
    assert "/candidates" in paths
    assert "/possibilities/explore" in paths
    selected = "/episodes/{episode_id}/actions/selected"
    admitted = "/episodes/{episode_id}/actions/admitted"
    legacy = "/episodes/{episode_id}/actions"
    assert selected in paths
    assert paths[selected]["post"].get("deprecated", False) is False
    assert paths[admitted]["post"]["deprecated"] is True
    assert paths[legacy]["post"]["deprecated"] is True


def test_contract_contains_crown_completion_schemas() -> None:
    contract = build_contract()
    assert contract.verify_digest()
    for key in (
        "broker_request",
        "candidate_intent_envelope",
        "replay_report",
        "safety_envelope",
        "fault_plan",
        "compile_out_report",
        "capsule_identity",
        "compiled_recipe",
        "decision_key",
        "differential_verification",
        "possibility_graph",
        "exploration_result",
        "irreversible_selection",
        "combinatorial_broker_request",
    ):
        assert key in contract.schemas


def test_real_memory_ledger_replays_without_actuation() -> None:
    ledger = MemoryReceiptLedger()
    ledger.append(
        Receipt(
            episode_id="ep-replay",
            operation=Operation.OBSERVE,
            standing=Standing.ALIVE,
            subject_ref="urn:subject:replay",
        )
    )
    report = replay_ledger(ledger, mode=ReplayMode.EVIDENCE_REPLAY)
    assert report.valid
    assert report.record_count == 1
    assert report.live_reexecution_admitted is False
