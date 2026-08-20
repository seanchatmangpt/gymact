"""Platform-console ontology-driven gym: a generated instance of
`gymact.gyms.ontology_gym`, the same mechanical composition
`gymact.gyms.togaf.build_togaf_provider` already uses -- not a hand-coded
environment.

Real pack consumed (`chatman-ecosystem/ontology/platform-console-gym-pack/
ontology.ttl`, eager-forging-sparrow plan Phase 4): three `sosa:Procedure`
individuals, the same bare-procedure shape `ontology_gym.load_procedures`
already extracts for `protocol-gym-pack` (no `pplan:Plan` wrapper, no
`dct:subject` artifact model) -- reusing the SAME individual IRIs as
`chatman-ecosystem/ontology/platform-console-capabilities.ttl`'s real
`ce:Capability` ABox (Phase 1 of the same plan), so a capability is one
identity across both graphs:

  - `pcc:CastleVerbInventoryComponents` (family `family-read`)
  - `pcc:CastleVerbInventoryGoals` (family `family-read`)
  - `pcc:ApprovalFreezeOverride` (family `family-approval`, elevated --
    matches that capability's own `ce:requiredAuthority
    "approval-workflow.requireApproval"` maker-checker gate)

`OntologyDrivenProvider.tasks()` only extracts `pplan:Plan` tasks
(`load_tasks`); this module's one override point is swapping that for
`load_procedures`, the bare-`sosa:Procedure` extractor `ontology_gym.py`
already ships for exactly this shape (`protocol-gym-pack`'s real
precedent) -- no change to `ontology_gym.py` itself, per the plan's explicit
"do not modify ontology_gym.py's core mechanism" boundary.

This module compiles the real, fact-based, authority-gated
`OntologyDrivenEnvironment` (in-process plan-state tracking + the same
`kernel.py` `AuthorityResolver`/`CapabilityScope` gates every other gym
goes through). It deliberately does NOT reimplement
`platform_console_provider.py`'s real HTTP/Bearer-key wiring -- a caller
driving a solved PDDL plan against real platform-console state composes
BOTH providers under one `GymAct` instance (this one for the
plan-state/authority-tier side, `PlatformConsoleProvider` unmodified for
the real HTTP side), exactly as
`tests/test_platform_console_ontology_driven_chicago.py` does.
"""

from __future__ import annotations

from pathlib import Path

from gymact.gyms.ontology_gym import OntologyDrivenProvider, OntologyTask, load_procedures

REPO_ROOT = Path(__file__).resolve().parents[3]
PLATFORM_CONSOLE_GYM_PACK_DIR = (
    REPO_ROOT.parent / "chatman-ecosystem" / "ontology" / "platform-console-gym-pack"
)

# Matches platform-console-capabilities.ttl's ce:requiredAuthority values
# exactly: freeze-override is gated by the maker-checker
# approval-workflow.requireApproval path; the two castle verbs are gated by
# the standard AuthorityObject.admits(castle.verb.run) broker admission.
ELEVATED_TASK_FAMILIES = frozenset({"family-approval"})


class PlatformConsoleOntologyDrivenProvider(OntologyDrivenProvider):
    """`OntologyDrivenProvider` configured for the bare-`sosa:Procedure`
    shape this pack uses (`load_procedures`) rather than the default
    `pplan:Plan` shape (`load_tasks`) -- the one real override this pack's
    shape requires, mirroring `ontology_gym.py`'s own documented distinction
    between the two extractors. No other method is touched; `materialize()`,
    `elevated_capability_iris()` and the whole `OntologyDrivenEnvironment`
    mechanism are inherited unmodified."""

    def tasks(self) -> tuple[OntologyTask, ...]:
        return load_procedures(self._pack_dir)


def build_platform_console_ontology_provider() -> PlatformConsoleOntologyDrivenProvider:
    """The entire platform-console-specific surface: pack location + one
    elevated family, over the generic compiler -- not a hand-coded
    environment."""
    return PlatformConsoleOntologyDrivenProvider(
        name="platform-console-ontology",
        pack_dir=PLATFORM_CONSOLE_GYM_PACK_DIR,
        elevated_task_families=ELEVATED_TASK_FAMILIES,
    )
