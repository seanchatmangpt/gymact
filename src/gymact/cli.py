"""Typer CLI for GymAct."""

from __future__ import annotations

import json

import anyio
import typer
import uvicorn

from gymact import __version__
from gymact.models import ActuationIntent
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


@app.command()
def demo(authority: bool = typer.Option(False, "--authority")) -> None:
    """Execute a deterministic bounded world transition and independent verification."""

    async def run() -> dict[str, object]:
        runtime = GymAct()
        runtime.register_provider(MemoryProvider(requires_authority=True))
        episode = await runtime.create_episode(
            "memory", config={"initial": {"healthy": False, "attempts": 0}}
        )
        intent = ActuationIntent(
            episode_id=episode.episode_id,
            affordance="set",
            payload={"key": "healthy", "value": True},
            authority_ref="urn:gymact:authority:demo" if authority else None,
            idempotency_key="demo-set-healthy",
        )
        actuation = await runtime.act(intent)
        verification = await runtime.verify(episode.episode_id, {"healthy": authority})
        return {
            "episode": episode.model_dump(mode="json"),
            "actuation": actuation.model_dump(mode="json"),
            "verification": verification.model_dump(mode="json"),
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
