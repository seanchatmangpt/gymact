"""gymact CLI."""

from __future__ import annotations

from importlib import resources

import typer
from pyshacl import validate
from rdflib import Graph
from rich import print as rprint

app = typer.Typer()


def _load_profile_graph() -> Graph:
    graph = Graph()
    ttl_path = resources.files("gymact.semantic").joinpath("profile.ttl")
    graph.parse(source=str(ttl_path), format="turtle")
    return graph


@app.command()
def validate_profile() -> None:
    """Validate the bundled GymAct semantic profile's SHACL shapes parse and are internally consistent."""
    graph = _load_profile_graph()
    conforms, _, report_text = validate(
        data_graph=graph,
        shacl_graph=graph,
        inference="none",
    )
    if conforms:
        rprint(f"[bold green]OK[/bold green] profile.ttl conforms ({len(graph)} triples).")
    else:
        rprint(f"[bold red]FAIL[/bold red]\n{report_text}")
        raise typer.Exit(code=1)
