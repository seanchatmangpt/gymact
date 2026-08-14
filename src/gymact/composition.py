"""Composition-admission gate: reuse-before-create law for GymAct providers.

Generalizes the discipline already proven by
`tests/test_registry_completeness_chicago.py` (mechanically ask "what actually
exists?" before trusting a hand-maintained list) one level up: from "is this
provider registered?" to "does a new provider need to be created at all, or does
an existing composition of GymAct components (providers, kernel gates, verifiers,
ggen packs) already supply the required capabilities?"

Decision lattice (five states, not four — this is the load-bearing correction over
an earlier draft that collapsed "not in the table" into "CREATE_PROVIDER"):

    REUSE             one existing component's own capabilities fully cover the
                       contract.
    COMPOSE           the contract is covered only by the union of >1 component.
    ADAPT             every residual capability is a capability this module has
                       explicitly classified as `"orchestration"` — control/wiring/
                       projection glue that composes existing world physics, not
                       new physics itself. Requires an explicit, evidenced
                       classification entry; never inferred.
    CREATE_PROVIDER   every residual capability is explicitly classified as
                       `"world_physics"` — new environment physics genuinely absent
                       from every known component. Also requires an explicit,
                       evidenced classification entry.
    BLOCKED_DISCOVERY at least one residual capability has NO classification entry
                       at all. This is the default and correct outcome for an
                       unrecognized capability id — it is UNKNOWN, not ABSENT, and
                       must never silently license CREATE_PROVIDER. Resolving a
                       BLOCKED_DISCOVERY result requires a human (or a future
                       discovery court) to add a real, evidenced classification
                       entry to `gymact.composition_inventory`, not a code change
                       to this module's decision logic.

Honesty boundary, stated explicitly so this module is never oversold: capability
matching here is NOT automatic semantic/NLP matching. Both the supply table
(`ComponentCapabilities`) and the classification table
(`CapabilityClassification`) in `gymact.composition_inventory` are hand-authored,
maintained the same way `registry.py`'s `_BUILTINS` and
`test_registry_completeness_chicago.py`'s `_INTENTIONALLY_UNREGISTERED` are: by a
human naming what a component really supplies and citing real evidence for it.

Mirrors the shape of `GymAct._authority_decision` (`gymact/kernel.py`): pure
decision functions returning a typed result, plus a raising assertion wrapper for
the enforcement half.
"""

from __future__ import annotations

from typing import Literal

from gymact.models import FrozenModel

Decision = Literal["REUSE", "COMPOSE", "ADAPT", "CREATE_PROVIDER", "BLOCKED_DISCOVERY"]

# Standings a claimed capability must carry to be trusted by the composition
# engine. A component whose evidence is only e.g. "UNKNOWN"/"BLOCKED" cannot
# silently contribute a capability as if it were live.
_TRUSTED_STANDINGS = frozenset({"ALIVE", "PARTIAL_ALIVE"})


class CapabilityEvidence(FrozenModel):
    """One component's claim to supply one capability, with the evidence backing
    that claim — not a bare string in a set."""

    capability_id: str
    evidence_ref: str
    evidence_kind: str
    standing: str
    subject_identity: str = ""


class ComponentCapabilities(FrozenModel):
    """What one existing, real GymAct component supplies, per evidenced claims."""

    component_ref: str
    capabilities: tuple[CapabilityEvidence, ...]

    @property
    def supplies(self) -> frozenset[str]:
        """Capability ids this component supplies at a trusted standing."""
        return frozenset(
            c.capability_id for c in self.capabilities if c.standing in _TRUSTED_STANDINGS
        )


class CapabilityClassification(FrozenModel):
    """An explicit, evidenced judgment about what KIND of gap a capability
    represents if no component supplies it. Absence of an entry here is what
    keeps an unmatched capability BLOCKED_DISCOVERY instead of CREATE_PROVIDER."""

    capability_id: str
    kind: Literal["world_physics", "orchestration"]
    reason: str


class CapabilityContract(FrozenModel):
    """A requirement: the set of capability-id strings a requester needs supplied."""

    name: str
    required_capabilities: frozenset[str]


class CompositionDecision(FrozenModel):
    """The real, derived outcome of matching a contract against an inventory."""

    contract_name: str
    covered_requirements: frozenset[str]
    residual_requirements: frozenset[str]
    unclassified_residual: frozenset[str]
    orchestration_residual: frozenset[str]
    physics_residual: frozenset[str]
    selected_components: tuple[str, ...]
    decision: Decision
    reason: str


class CreateNotAuthorized(RuntimeError):
    """Raised when CREATE_PROVIDER is attempted but the mechanical decision is
    not CREATE_PROVIDER — either an existing composition already covers the
    contract, adaptation suffices, or discovery is incomplete."""


def compute_residual(
    contract: CapabilityContract,
    inventory: tuple[ComponentCapabilities, ...],
    classifications: tuple[CapabilityClassification, ...] = (),
) -> CompositionDecision:
    """Pure function. Diffs `contract.required_capabilities` against the union of
    every trusted-standing capability in `inventory`, then classifies any residual
    using `classifications` — never inferring a classification that wasn't given.
    """
    selected: list[str] = []
    covered: set[str] = set()
    for component in inventory:
        overlap = component.supplies & contract.required_capabilities
        if overlap - covered:
            selected.append(component.component_ref)
            covered |= overlap

    residual = frozenset(contract.required_capabilities - covered)
    by_id = {c.capability_id: c for c in classifications}

    unclassified = frozenset(cap for cap in residual if cap not in by_id)
    orchestration = frozenset(
        cap for cap in residual if by_id.get(cap) and by_id[cap].kind == "orchestration"
    )
    physics = frozenset(
        cap for cap in residual if by_id.get(cap) and by_id[cap].kind == "world_physics"
    )

    decision: Decision
    if not residual:
        if len(selected) <= 1:
            decision = "REUSE"
            reason = "a single existing component's capabilities fully cover the contract"
        else:
            decision = "COMPOSE"
            reason = (
                f"contract is covered only by composing {len(selected)} existing "
                "components; no single component suffices"
            )
    elif unclassified:
        decision = "BLOCKED_DISCOVERY"
        reason = (
            "residual capabilities have no evidenced classification entry — "
            f"UNKNOWN, not proven absent, so CREATE_PROVIDER is refused: {sorted(unclassified)}"
        )
    elif physics:
        decision = "CREATE_PROVIDER"
        reason = (
            "residual capabilities are explicitly classified as new world physics "
            f"absent from every known component: {sorted(physics)}"
        )
    else:
        decision = "ADAPT"
        reason = (
            "residual capabilities are explicitly classified as orchestration/"
            f"wiring only — existing physics suffice: {sorted(orchestration)}"
        )

    return CompositionDecision(
        contract_name=contract.name,
        covered_requirements=frozenset(covered),
        residual_requirements=residual,
        unclassified_residual=unclassified,
        orchestration_residual=orchestration,
        physics_residual=physics,
        selected_components=tuple(selected),
        decision=decision,
        reason=reason,
    )


def assert_create_authorized(
    contract: CapabilityContract,
    inventory: tuple[ComponentCapabilities, ...],
    classifications: tuple[CapabilityClassification, ...] = (),
) -> CompositionDecision:
    """Enforcement half. Raises `CreateNotAuthorized` unless the mechanically
    derived decision is `CREATE_PROVIDER` — i.e. a real residual exists AND every
    residual capability has been explicitly, evidently classified as new world
    physics. `BLOCKED_DISCOVERY` refuses just as hard as `REUSE`/`COMPOSE`/`ADAPT`
    do: incomplete discovery is never grounds to create."""
    result = compute_residual(contract, inventory, classifications)
    if result.decision != "CREATE_PROVIDER":
        raise CreateNotAuthorized(
            f"CREATE refused for contract {contract.name!r}: {result.reason}. "
            f"Compose/adapt existing components instead: {result.selected_components}"
        )
    return result
