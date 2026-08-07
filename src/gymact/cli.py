"""Typer CLI for GymAct."""

from __future__ import annotations

import json
from pathlib import Path

import anyio
import typer
import uvicorn

from gymact import __version__
from gymact.authority import AllowListAuthorityResolver
from gymact.contract import build_contract
from gymact.manufacture import export_manufacturing_bundle
from gymact.models import ActuationIntent, MaterializationIntent
from gymact.providers import MemoryProvider
from gymact.runtime import GymAct
from gymact.semantic import ProfileAuthority
from gymact.surfaces.fastapi import create_app

app = typer.Typer(no_args_is_help=True, help="GymAct bounded benchmark-world execution")


@app.command()
def version() -> None:
    """Print the package version."""
    typer.echo(__version__)


@app.command()
def contract() -> None:
    """Print the self-digested runtime contract for independent consumers."""
    typer.echo(json.dumps(build_contract().model_dump(mode="json"), sort_keys=True))


@app.command("validate-profile")
def validate_profile() -> None:
    """Run SHACL and zero-custom-TBox validation against the packaged profile."""
    result = ProfileAuthority().validate()
    typer.echo(json.dumps(result.model_dump(mode="json"), sort_keys=True))
    if not result.conforms:
        raise typer.Exit(code=2)


@app.command("export-profile")
def export_profile(directory: Path) -> None:
    """Export the admitted RDF/SHACL profile, with per-file digests, for
    ggen or another compiler to consume and mechanically verify."""
    authority = ProfileAuthority()
    exported = authority.export(directory)
    payload = {
        "profile_uri": authority.profile_uri,
        "files": {
            name: {"path": str(resource.path), "sha256": resource.sha256}
            for name, resource in exported.items()
        },
    }
    typer.echo(json.dumps(payload, sort_keys=True))


@app.command("export-bundle")
def export_bundle(directory: Path) -> None:
    """Export RDF/SHACL plus RFC8785 runtime contract, with per-file digests,
    for ggen/Rust manufacture to consume and mechanically verify."""
    exported = export_manufacturing_bundle(directory)
    payload = {
        name: {"path": str(resource.path), "sha256": resource.sha256}
        for name, resource in exported.items()
    }
    typer.echo(json.dumps(payload, sort_keys=True))


@app.command()
def demo(authority: bool = typer.Option(False, "--authority")) -> None:
    """Execute a deterministic bounded world transition and independent verification."""

    async def run() -> dict[str, object]:
        authority_ref = "urn:gymact:authority:demo"
        runtime = GymAct(
            authority_resolver=AllowListAuthorityResolver({authority_ref}) if authority else None
        )
        runtime.register_provider(MemoryProvider(requires_authority=True))
        materialized = await runtime.materialize(
            MaterializationIntent(
                provider="memory",
                config={"initial": {"healthy": False, "attempts": 0}},
                idempotency_key="demo-materialize",
            )
        )
        if materialized.episode is None:
            return {"materialization": materialized.model_dump(mode="json")}
        episode = materialized.episode
        intent = ActuationIntent(
            episode_id=episode.episode_id,
            capability="urn:gymact:memory:capability:set",
            payload={"key": "healthy", "value": True},
            authority_ref=authority_ref if authority else None,
            idempotency_key="demo-set-healthy",
        )
        actuation = await runtime.act(intent)
        verification = await runtime.verify(episode.episode_id, {"healthy": authority})
        return {
            "materialization": materialized.model_dump(mode="json"),
            "actuation": actuation.model_dump(mode="json"),
            "verification": verification.model_dump(mode="json"),
            "evidence_verified": runtime.verify_evidence_chain(),
        }

    typer.echo(json.dumps(anyio.run(run), sort_keys=True))


@app.command()
def serve(
    host: str = typer.Option("127.0.0.1"),
    port: int = typer.Option(8000, min=1, max=65535),
) -> None:
    """Run the FastAPI/OpenAPI surface with the deterministic reference provider."""
    runtime = GymAct()
    runtime.register_provider(MemoryProvider())
    uvicorn.run(create_app(runtime), host=host, port=port)
