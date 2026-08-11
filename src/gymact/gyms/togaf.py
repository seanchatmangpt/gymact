"""TOGAF ADM gym: a generated instance of `gymact.gyms.ontology_gym`.

Not a hand-coded environment. The full 10-phase TOGAF ADM topology
(Preliminary through Phase H, real precondition chain, real multi-subject
tasks, real authority tiers, real Phase H -> Requirements Management
loop-back) is compiled at `materialize()` time directly from
`ggen/togaf-gym-pack/ontology.ttl`'s ten already-real `pplan:Plan` task
instances -- unmodified by this module. See
`gymact.gyms.ontology_gym`'s module docstring for the derivation rules and
`docs/prd/v26.8.11-togaf-fortune5-adm-gym.md`'s "Architecture correction"
section for why this replaced an earlier, hand-coded, per-phase M1 slice.

`task-family:governance` (Phase G) and `task-family:change` (Phase H) are
configured here as the two elevated-authority families -- TOGAF's own
Architecture Board / change-control separation, enforced by a
`TieredAuthorityResolver` a caller injects, never by this module deciding
authority itself. `task-family:change` is also configured as the reset
family that reopens `task-family:requirements`' facts -- the real, checkable
form of TOGAF's own cyclical ADM structure (Phase H feeds back into
Requirements Management, not a terminal state).
"""

from __future__ import annotations

from pathlib import Path

from gymact.gyms.ontology_gym import OntologyDrivenProvider

REPO_ROOT = Path(__file__).resolve().parents[3]
TOGAF_PACK_DIR = REPO_ROOT / "ggen" / "togaf-gym-pack"

ELEVATED_TASK_FAMILIES = frozenset({"governance", "change"})
RESET_TASK_FAMILIES = frozenset({"change"})
RESET_TARGET_FAMILIES = frozenset({"requirements"})


def build_togaf_provider() -> OntologyDrivenProvider:
    """The entire TOGAF-specific surface: five lines of configuration over
    the generic compiler, not a hand-coded environment."""
    return OntologyDrivenProvider(
        name="togaf",
        pack_dir=TOGAF_PACK_DIR,
        elevated_task_families=ELEVATED_TASK_FAMILIES,
        reset_task_families=RESET_TASK_FAMILIES,
        reset_target_families=RESET_TARGET_FAMILIES,
    )


# Backward-compatible alias: gymact.register_provider(TogafProvider()) reads
# the same as before M1's hand-coded environment was replaced by the
# generator, without importing the class directly.
TogafProvider = build_togaf_provider
