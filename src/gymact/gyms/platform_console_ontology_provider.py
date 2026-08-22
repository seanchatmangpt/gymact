"""Platform-console ontology-driven gym.

The provider compiles the platform-console semantic pack through the generic
ontology gym mechanism. Runtime authority remains in GymAct/BRCE; pack
location is an observation/admission concern only.
"""

from __future__ import annotations

import os
from pathlib import Path

from gymact.gyms.ontology_gym import OntologyDrivenProvider, OntologyTask, load_procedures
from gymact.gyms.semantic_pack_locator import resolve_semantic_pack

REPO_ROOT = Path(__file__).resolve().parents[3]
PLATFORM_CONSOLE_GYM_PACK_DIR = (
    REPO_ROOT.parent / "chatman-ecosystem" / "ontology" / "platform-console-gym-pack"
)
PLATFORM_CONSOLE_PACK_ENV = "GYMACT_PLATFORM_CONSOLE_PACK_DIR"

ELEVATED_TASK_FAMILIES = frozenset({"family-approval"})


class PlatformConsoleOntologyDrivenProvider(OntologyDrivenProvider):
    """Provider for the pack's bare-``sosa:Procedure`` semantic shape."""

    def tasks(self) -> tuple[OntologyTask, ...]:
        return load_procedures(self._pack_dir)


def resolve_default_platform_console_pack_dir() -> Path:
    """Resolve portable default locations without silently preferring drift.

    The historical sibling-repository path remains a candidate. A caller may
    additionally materialize the same pack elsewhere and expose its directory
    through ``GYMACT_PLATFORM_CONSOLE_PACK_DIR``. If both exist, they must be
    byte-equivalent at ``ontology.ttl`` or resolution refuses.

    When neither is materialized we preserve the predecessor's delayed
    ``NO_TASKS_FOUND_IN_PACK`` behavior by returning the canonical sibling
    path; this keeps missing-source failure semantics backward compatible.
    """

    candidates = [PLATFORM_CONSOLE_GYM_PACK_DIR]
    configured = os.environ.get(PLATFORM_CONSOLE_PACK_ENV)
    if configured:
        candidates.append(Path(configured))

    try:
        return resolve_semantic_pack(candidates=candidates).path
    except ValueError as exc:
        if str(exc) == "REFUSED_NO_SEMANTIC_PACK_MATERIALIZED":
            return PLATFORM_CONSOLE_GYM_PACK_DIR
        raise


def build_platform_console_ontology_provider(
    *, pack_dir: Path | None = None
) -> PlatformConsoleOntologyDrivenProvider:
    """Compile the admitted platform-console semantic pack.

    Explicit ``pack_dir`` remains the strongest reversible caller choice.
    Without one, the portable resolver admits equivalent materialized
    locations and refuses divergent ambiguity. No choice grants actuation
    authority or changes the provider's authority tiers.
    """

    admitted_pack_dir = resolve_default_platform_console_pack_dir() if pack_dir is None else pack_dir
    return PlatformConsoleOntologyDrivenProvider(
        name="platform-console-ontology",
        pack_dir=admitted_pack_dir,
        elevated_task_families=ELEVATED_TASK_FAMILIES,
    )
