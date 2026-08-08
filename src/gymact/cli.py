"""Typer CLI for GymAct."""
from __future__ import annotations

import importlib.util
import json
import shutil
from pathlib import Path
from typing import Any

import anyio
import typer
import uvicorn

from gymact import __version__
from gymact.action_contract import (
    ActionDefinition,
    ExecutionGrant,
    ReconciliationResult,
    SubjectRef,
    admit_retry,
    construct_prepared_action,
)
from gymact.authority import AllowListAuthorityResolver
from gymact.brce import BRCEBroker, BrokerRequest
from gymact.contract import build_contract
from gymact.experiments import AntiAgentPoint, anti_agent_benchmark
from gymact.manufacture import export_manufacturing_bundle
from gymact.models import ActuationIntent, MaterializationIntent
from gymact.registry import (
    builtin_capabilities,
    builtin_provider_names,
    create_builtin_provider,
    describe_builtin_provider,
)
from gymact.replay import ReplayExpectation, ReplayMode, replay_ledger
from gymact.requirements import crown_summary, load_crown_requirements
from gymact.runtime import GymAct
from gymact.semantic import ProfileAuthority
from gymact.sqlite_ledger import SQLiteReceiptLedger
from gymact.surfaces.fastapi import create_app
from gymact.transport import TransportKind, normalize_candidate

app = typer.Typer(no_args_is_help=True, help="GymAct lawful executable-world runtime")


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise typer.BadParameter("JSON request must be an object")
    return value


def _echo(value: object) -> None:
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    typer.echo(json.dumps(value, sort_keys=True, default=str))


def _runtime(provider_name: str, authority_refs: set[str] | None = None) -> GymAct:
    refs = authority_refs or set()
    resolver = AllowListAuthorityResolver(refs) if refs else None
    runtime = GymAct(authority_resolver=resolver)
    runtime.register_provider(create_builtin_provider(provider_name))
    return runtime


async def _materialize_request(data: dict[str, Any]) -> tuple[GymAct, object]:
    provider_name = str(data.get("provider", "memory"))
    authority_ref = data.get("materialization_authority_ref")
    refs = {str(authority_ref)} if authority_ref else set()
    grant_data = data.get("grant")
    if isinstance(grant_data, dict) and grant_data.get("authority_ref"):
        refs.add(str(grant_data["authority_ref"]))
    runtime = _runtime(provider_name, refs)
    result = await runtime.materialize(
        MaterializationIntent(
            provider=provider_name,
            scenario=data.get("scenario"),
            config=data.get("config", {}),
            authority_ref=str(authority_ref) if authority_ref else None,
            idempotency_key=str(data.get("materialization_idempotency_key", "cli-materialize")),
        )
    )
    return runtime, result


@app.command()
def version() -> None:
    """Print the package version."""
    typer.echo(__version__)


@app.command()
def contract() -> None:
    """Print the self-digested runtime contract for independent consumers."""
    _echo(build_contract())


@app.command("crown-status")
def crown_status() -> None:
    """Print the evidence-bounded Crown build queue and current GALL blockers."""
    _echo(crown_summary().as_dict())


@app.command("requirements")
def requirements_inventory() -> None:
    """Print the canonical P0/P1/P2 requirements and CP0-CP16 inventory."""
    _echo(load_crown_requirements())


@app.command("providers")
def providers() -> None:
    """List built-in provider families; plugin providers remain separately discoverable."""
    _echo({"builtins": builtin_provider_names()})


@app.command("capabilities")
def capabilities(provider: str) -> None:
    """Inspect semantic capabilities without materializing or actuating a world."""
    _echo(
        {
            "provider": provider,
            "capabilities": [
                item.model_dump(mode="json") for item in builtin_capabilities(provider)
            ],
        }
    )


@app.command("inspect")
def inspect_provider(provider: str) -> None:
    """Inspect one built-in provider's declared mechanics without granting authority."""
    _echo(describe_builtin_provider(provider))


@app.command("prepare")
def prepare(
    request: Path,
    transport: str = typer.Option("cli", help="Candidate-intent transport identity"),
) -> None:
    """CONSTRUCT a powerless PreparedAction from a transport-neutral JSON request."""
    try:
        kind = TransportKind(transport)
    except ValueError as exc:
        raise typer.BadParameter(f"unknown transport: {transport}") from exc
    envelope = normalize_candidate(kind, _read_json(request))
    _echo(
        {
            "transport": envelope.transport.value,
            "semantic_key": envelope.semantic_key(),
            "prepared": envelope.prepared().model_dump(mode="json"),
        }
    )


@app.command("execute")
def execute(request: Path) -> None:
    """Execute one admitted action through the BRCE production DO facade."""
    data = _read_json(request)

    async def run() -> dict[str, Any]:
        runtime, materialized = await _materialize_request(data)
        payload = materialized.model_dump(mode="json")
        if materialized.episode is None:
            return {"materialization": payload}
        action = ActionDefinition.model_validate(data["action"])
        subject = SubjectRef.model_validate(data["subject"])
        grant = ExecutionGrant.model_validate(data["grant"])
        prepared = construct_prepared_action(
            action,
            episode_id=materialized.episode.episode_id,
            subject=subject,
            payload=data.get("payload", {}),
            admission_digest=str(data["admission_digest"]),
            idempotency_key=str(data.get("idempotency_key", "cli-execute")),
        )
        transition = await BRCEBroker(runtime).execute(
            BrokerRequest(
                action=action,
                prepared=prepared,
                grant=grant,
                current_revision=data.get("current_revision"),
                expected=data.get("expected", {}),
            )
        )
        return {
            "materialization": payload,
            "transition": transition.model_dump(mode="json"),
            "evidence_verified": runtime.verify_evidence_chain(),
        }

    _echo(anyio.run(run))


@app.command("observe")
def observe(request: Path) -> None:
    """Materialize a configured subject and independently observe its current state."""
    data = _read_json(request)

    async def run() -> dict[str, Any]:
        runtime, materialized = await _materialize_request(data)
        if materialized.episode is None:
            return {"materialization": materialized.model_dump(mode="json")}
        observation = await runtime.observe(materialized.episode.episode_id)
        return {"observation": observation.model_dump(mode="json")}

    _echo(anyio.run(run))


@app.command("verify")
def verify(request: Path) -> None:
    """Materialize a configured subject and verify an expected current postcondition."""
    data = _read_json(request)

    async def run() -> dict[str, Any]:
        runtime, materialized = await _materialize_request(data)
        if materialized.episode is None:
            return {"materialization": materialized.model_dump(mode="json")}
        result = await runtime.verify(
            materialized.episode.episode_id,
            data.get("expected", {}),
        )
        return {"verification": result.model_dump(mode="json")}

    _echo(anyio.run(run))


@app.command("reconcile")
def reconcile(request: Path) -> None:
    """Admit or refuse a retry after an independently observed reconciliation result."""
    data = _read_json(request)
    action = ActionDefinition.model_validate(data["action"])
    result = ReconciliationResult.model_validate(data["reconciliation"])
    _echo(admit_retry(action, result))


@app.command("replay")
def replay(
    ledger: Path,
    mode: str = typer.Option("EVIDENCE_REPLAY"),
    subject_ref: str | None = None,
    capability_ref: str | None = None,
    policy_revision: str | None = None,
    principal: str | None = None,
    allow_live_reexecution: bool = False,
) -> None:
    """Replay evidence/verifier identity; live re-execution is refused by default."""
    try:
        replay_mode = ReplayMode(mode)
    except ValueError as exc:
        raise typer.BadParameter(f"unknown replay mode: {mode}") from exc
    expectation = ReplayExpectation(
        subject_ref=subject_ref,
        capability_ref=capability_ref,
        policy_revision=policy_revision,
        principal=principal,
    )
    with SQLiteReceiptLedger(ledger) as receipt_ledger:
        report = replay_ledger(
            receipt_ledger,
            mode=replay_mode,
            expected=expectation,
            allow_live_reexecution=allow_live_reexecution,
        )
    _echo(report)


@app.command("benchmark")
def benchmark(request: Path) -> None:
    """Evaluate anti-agent crossover and marginal-cost economics from JSON evidence."""
    data = _read_json(request)
    points = tuple(AntiAgentPoint.model_validate(item) for item in data.get("points", ()))
    _echo(anti_agent_benchmark(points))


@app.command("doctor")
def doctor() -> None:
    """Report local execution prerequisites without upgrading their standing."""
    modules = ("blake3", "fastapi", "fastmcp", "faststream", "pyshacl", "rfc8785")
    payload = {
        "git": shutil.which("git") is not None,
        "modules": {name: importlib.util.find_spec(name) is not None for name in modules},
        "providers": builtin_provider_names(),
        "crown": crown_summary().as_dict(),
    }
    _echo(payload)


@app.command("validate-profile")
def validate_profile() -> None:
    """Run SHACL and zero-custom-TBox validation against the packaged profile."""
    result = ProfileAuthority().validate()
    _echo(result)
    if not result.conforms:
        raise typer.Exit(code=2)


@app.command("export-profile")
def export_profile(directory: Path) -> None:
    """Export the admitted RDF/SHACL profile with per-file digests."""
    authority = ProfileAuthority()
    exported = authority.export(directory)
    _echo(
        {
            "profile_uri": authority.profile_uri,
            "files": {
                name: {"path": str(resource.path), "sha256": resource.sha256}
                for name, resource in exported.items()
            },
        }
    )


@app.command("export-bundle")
def export_bundle(directory: Path) -> None:
    """Export RDF/SHACL plus the RFC8785 runtime contract for manufacture."""
    exported = export_manufacturing_bundle(directory)
    _echo(
        {
            name: {"path": str(resource.path), "sha256": resource.sha256}
            for name, resource in exported.items()
        }
    )


@app.command()
def demo(authority: bool = typer.Option(False, "--authority")) -> None:
    """Execute a deterministic bounded transition; retained as a development example."""

    async def run() -> dict[str, object]:
        authority_ref = "urn:gymact:authority:demo"
        runtime = _runtime("memory", {authority_ref} if authority else set())
        materialized = await runtime.materialize(
            MaterializationIntent(
                provider="memory",
                config={"initial": {"healthy": False, "attempts": 0}},
                idempotency_key="demo-materialize",
            )
        )
        if materialized.episode is None:
            return {"materialization": materialized.model_dump(mode="json")}
        intent = ActuationIntent(
            episode_id=materialized.episode.episode_id,
            capability="urn:gymact:memory:capability:set",
            payload={"key": "healthy", "value": True},
            authority_ref=authority_ref if authority else None,
            idempotency_key="demo-set-healthy",
        )
        actuation = await runtime.act(intent)
        verification = await runtime.verify(
            materialized.episode.episode_id, {"healthy": authority}
        )
        return {
            "materialization": materialized.model_dump(mode="json"),
            "actuation": actuation.model_dump(mode="json"),
            "verification": verification.model_dump(mode="json"),
            "evidence_verified": runtime.verify_evidence_chain(),
        }

    _echo(anyio.run(run))


@app.command()
def serve(
    host: str = typer.Option("127.0.0.1"),
    port: int = typer.Option(8000, min=1, max=65535),
) -> None:
    """Run the FastAPI/OpenAPI surface with the deterministic reference provider."""
    runtime = GymAct()
    runtime.register_provider(create_builtin_provider("memory"))
    uvicorn.run(create_app(runtime), host=host, port=port)
