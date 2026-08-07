"""Typer CLI for GymAct."""

from __future__ import annotations

import json
from pathlib import Path

import anyio
import typer
import uvicorn

from gymact import __version__
from gymact.authority import AllowListAuthorityResolver
from gymact.contract import contract_document
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


@app.command("validate-profile")
def validate_profile() -> None:
    """Run SHACL and zero-custom-TBox validation against the packaged profile."""
    result = ProfileAuthority().validate()
    typer.echo(json.dumps(result.model_dump(mode="json"), sort_keys=True))
    if not result.conforms:
        raise typer.Exit(code=2)


@app.command("export-profile")
def export_profile(directory: Path) -> None:
    """Export the admitted RDF/SHACL profile for ggen or another compiler."""
    paths = ProfileAuthority().export(directory)
    typer.echo(json.dumps({key: str(value) for key, value in paths.items()}, sort_keys=True))


@app.command("export-contract")
def export_contract(path: Path | None = None) -> None:
    """Export the portable JSON-schema contract for ggen or another compiler."""
    payload = json.dumps(contract_document(), indent=2, sort_keys=True) + "\n"
    if path is None:
        typer.echo(payload, nl=False)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload, encoding="utf-8")
    typer.echo(str(path))


@app.command()
def demo(authority: bool = typer.Option(False, "--authority")) -> None:
    """Execute a deterministic bounded world transition and independent verification."""

    async def run() -> dict[str, object]:
        authority_ref = "urn:gymact:authority:demo"
        runtime = GymAct(
            authority_resolver=AllowListAuthorityResolver({authority_ref})
            if authority
            else None
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
            "evidence_chain_valid": await runtime.verify_evidence_chain(),
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
