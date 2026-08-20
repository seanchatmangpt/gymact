from __future__ import annotations

import json

from fastapi.testclient import TestClient
from typer.testing import CliRunner

from gymact import GymAct, MemoryProvider, build_contract
from gymact.cli import app as cli_app
from gymact.surfaces.fastapi import create_app


def test_fastapi_contract_and_evidence_share_runtime_identity() -> None:
    runtime = GymAct()
    runtime.register_provider(MemoryProvider())
    # Own the TestClient portal/lifespan for the exact duration of this test.
    # Deferred close() finalizers can leave AnyIO streams/event-loop sockets
    # observable by pytest's later unraisable-exception collection.
    with TestClient(create_app(runtime)) as client:
        health = client.get("/health")
        assert health.status_code == 200
        assert health.json()["contract_digest"] == build_contract().contract_digest

        contract = client.get("/contract")
        assert contract.status_code == 200
        assert contract.json()["contract_digest"] == build_contract().contract_digest
        assert contract.json()["canonicalization"] == "RFC8785-JCS"

        evidence = client.get("/evidence")
        assert evidence.status_code == 200
        assert evidence.json() == {"verified": True, "records": []}

        prov = client.get("/evidence/prov")
        assert prov.status_code == 200
        assert prov.headers["content-type"].startswith("text/turtle")


def test_cli_contract_and_manufacturing_bundle_are_same_contract(tmp_path) -> None:
    runner = CliRunner()
    contract_result = runner.invoke(cli_app, ["contract"])
    assert contract_result.exit_code == 0
    observed = json.loads(contract_result.stdout)
    assert observed["contract_digest"] == build_contract().contract_digest

    output = tmp_path / "bundle"
    exported = runner.invoke(cli_app, ["export-bundle", str(output)])
    assert exported.exit_code == 0
    assert (output / "profile.ttl").exists()
    assert (output / "profile.shacl.ttl").exists()
    assert (output / "runtime-contract.jcs.json").exists()
    bundle = json.loads((output / "runtime-contract.jcs.json").read_bytes())
    assert bundle["contract_digest"] == observed["contract_digest"]
