"""Synthetic merger-and-acquisition gym compiled from ``mna-gym-pack``.

The environment contains no real issuer, security, company, board authority,
or external transaction endpoint.  It is an executable institutional world
for Fortune-scale planning/benchmark episodes.  Analysis tasks use standard
synthetic authority; governance and simulated close use a distinct elevated
authority tier.
"""
from __future__ import annotations

from pathlib import Path

from gymact.gyms.ontology_gym import OntologyDrivenProvider

REPO_ROOT = Path(__file__).resolve().parents[3]
MNA_PACK_DIR = REPO_ROOT / "ggen" / "mna-gym-pack"

ELEVATED_TASK_FAMILIES = frozenset({"governance", "simulated-close"})


def build_mna_provider() -> OntologyDrivenProvider:
    """Compile the complete M&A process directly from the admitted ontology."""
    return OntologyDrivenProvider(
        name="mna",
        pack_dir=MNA_PACK_DIR,
        elevated_task_families=ELEVATED_TASK_FAMILIES,
    )


MnaProvider = build_mna_provider
