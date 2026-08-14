"""Hand-authored, evidenced capability tables for `gymact.composition`.

Both tables here are maintained by hand, exactly like `registry.py`'s
`_BUILTINS` dict and `tests/test_registry_completeness_chicago.py`'s
`_INTENTIONALLY_UNREGISTERED` reasons: a human names what a real,
already-verified GymAct component supplies, and — separately — names what KIND
of gap a capability represents if nothing supplies it. A capability absent from
BOTH tables reads as `UNKNOWN` (→ `BLOCKED_DISCOVERY` in `gymact.composition`),
never as proven absent — the same epistemic stance this repo already takes
toward a stale Lumen index (`.claude/rules/tools.md`).

Every `component_ref` below points at a class or module-level function pair
directly verified against current source; every `evidence_ref` is a real
file:line span (see `.claude/plans/yes-gymact-is-exactly-purrfect-shell.md` for
the verification record). Capability ids are deliberately narrow — they name
one mechanism, not a desired conclusion (e.g. `RECEIPTED_EFFECT_PORT`, not
`ENUMERATE_EFFECT_SURFACE`; a receipted effect boundary is not the same claim as
proven completeness of an effect surface).
"""

from __future__ import annotations

from gymact.composition import (
    CapabilityClassification,
    CapabilityEvidence,
    ComponentCapabilities,
)

KNOWN_COMPONENT_CAPABILITIES: tuple[ComponentCapabilities, ...] = (
    ComponentCapabilities(
        component_ref="gymact.gyms.swegym.SWEGymProvider",
        capabilities=(
            CapabilityEvidence(
                capability_id="MATERIALIZE_ISOLATED_SUBJECT",
                evidence_ref="src/gymact/gyms/swegym.py:551-641",
                evidence_kind="source-contract",
                standing="ALIVE",
                subject_identity="swegym",
            ),
            CapabilityEvidence(
                capability_id="INDEPENDENT_WORLD_OBSERVATION",
                evidence_ref="src/gymact/gyms/swegym.py:217-236",
                evidence_kind="source-contract",
                standing="ALIVE",
                subject_identity="swegym",
            ),
            CapabilityEvidence(
                capability_id="UPSTREAM_HELD_OUT_GRADING",
                evidence_ref="src/gymact/gyms/swegym.py:145-155,434-494",
                evidence_kind="source-contract",
                standing="ALIVE",
                subject_identity="swegym",
            ),
        ),
    ),
    ComponentCapabilities(
        component_ref="gymact.gyms.sregym.SregymVendorProvider",
        capabilities=(
            CapabilityEvidence(
                capability_id="MATERIALIZE_ISOLATED_SUBJECT",
                evidence_ref="src/gymact/gyms/sregym.py:1025-1035",
                evidence_kind="source-contract",
                standing="ALIVE",
                subject_identity="sregym",
            ),
            CapabilityEvidence(
                capability_id="AUTHORITY_GATE",
                evidence_ref="src/gymact/gyms/sregym.py:94-237,1025-1035",
                evidence_kind="source-contract",
                standing="ALIVE",
                subject_identity="sregym",
            ),
            CapabilityEvidence(
                capability_id="INDEPENDENT_WORLD_OBSERVATION",
                evidence_ref="src/gymact/gyms/sregym.py:650-670",
                evidence_kind="source-contract",
                standing="ALIVE",
                subject_identity="sregym",
            ),
            CapabilityEvidence(
                capability_id="OCEL_EMISSION",
                evidence_ref="src/gymact/ocel.py:33-160 (via kernel receipts)",
                evidence_kind="source-contract",
                standing="ALIVE",
                subject_identity="sregym",
            ),
        ),
    ),
    ComponentCapabilities(
        component_ref="gymact.gyms.kubernetes_reconciliation.KubernetesReconciliationProvider",
        capabilities=(
            CapabilityEvidence(
                capability_id="MATERIALIZE_ISOLATED_SUBJECT",
                evidence_ref="src/gymact/gyms/kubernetes_reconciliation.py:145-179",
                evidence_kind="source-contract",
                standing="ALIVE",
                subject_identity="kubernetes-reconciliation",
            ),
            CapabilityEvidence(
                capability_id="INDEPENDENT_WORLD_OBSERVATION",
                evidence_ref="src/gymact/gyms/kubernetes_reconciliation.py:194-206",
                evidence_kind="source-contract",
                standing="ALIVE",
                subject_identity="kubernetes-reconciliation",
            ),
        ),
    ),
    ComponentCapabilities(
        component_ref="gymact.agent.AllowListCapabilityScope",
        capabilities=(
            CapabilityEvidence(
                capability_id="CAPABILITY_SCOPE_GATE",
                evidence_ref="src/gymact/agent.py:71-90; src/gymact/kernel.py:679-701",
                evidence_kind="source-contract",
                standing="ALIVE",
            ),
        ),
    ),
    ComponentCapabilities(
        component_ref="gymact.authority.AllowListAuthorityResolver",
        capabilities=(
            CapabilityEvidence(
                capability_id="AUTHORITY_GATE",
                evidence_ref="src/gymact/authority.py:32-52",
                evidence_kind="source-contract",
                standing="ALIVE",
            ),
        ),
    ),
    ComponentCapabilities(
        component_ref="gymact.authority.DenyAuthorityResolver",
        capabilities=(
            CapabilityEvidence(
                capability_id="FAIL_CLOSED_REFUSAL",
                evidence_ref="src/gymact/authority.py:23-30",
                evidence_kind="source-contract",
                standing="ALIVE",
            ),
        ),
    ),
    ComponentCapabilities(
        component_ref="gymact.verification.PostconditionVerifier",
        capabilities=(
            CapabilityEvidence(
                capability_id="INDEPENDENT_POSTCONDITION_JUDGMENT",
                evidence_ref="src/gymact/verification.py:64-83; src/gymact/kernel.py:836-890",
                evidence_kind="source-contract",
                standing="ALIVE",
            ),
        ),
    ),
    ComponentCapabilities(
        # Real, concrete default judge (the Protocol entry above documents the
        # contract; this entry is the actual class the kernel constructs when no
        # verifier is injected). Found uncataloged by the Court A inventory scan
        # (tests/test_composition_inventory_completeness_chicago.py), added
        # 2026-08-14 with real evidence rather than allowlisted, since it is the
        # concrete, load-bearing default -- not a permissive/optional stand-in.
        component_ref="gymact.verification.DictSubsetVerifier",
        capabilities=(
            CapabilityEvidence(
                capability_id="INDEPENDENT_POSTCONDITION_JUDGMENT",
                evidence_ref="src/gymact/verification.py:86-101",
                evidence_kind="source-contract",
                standing="ALIVE",
            ),
        ),
    ),
    ComponentCapabilities(
        # Alternate concrete judge for RDF/SHACL-shaped observed state, distinct
        # capability id from the plain-dict judge above since it requires a
        # graph-shaped `observed` and refuses cleanly otherwise (verification.py
        # docstring). Found uncataloged by the Court A inventory scan, added
        # 2026-08-14.
        component_ref="gymact.verification.ShaclPostconditionVerifier",
        capabilities=(
            CapabilityEvidence(
                capability_id="SHACL_POSTCONDITION_JUDGMENT",
                evidence_ref="src/gymact/verification.py:104-160",
                evidence_kind="source-contract",
                standing="ALIVE",
            ),
        ),
    ),
    ComponentCapabilities(
        component_ref="gymact.world.BRCEEffectPort",
        capabilities=(
            CapabilityEvidence(
                capability_id="RECEIPTED_EFFECT_PORT",
                evidence_ref="src/gymact/world.py:214-319",
                evidence_kind="source-contract",
                standing="ALIVE",
            ),
        ),
    ),
    ComponentCapabilities(
        # Distinct from validate_ocel_log/write_ocel_log below: this is the real
        # construction step (Receipt trail -> OCEL 2.0 log dict) those two
        # functions consume/persist/validate. Found uncataloged by the Court A
        # inventory scan, added 2026-08-14.
        component_ref="gymact.ocel.receipts_to_ocel",
        capabilities=(
            CapabilityEvidence(
                capability_id="OCEL_EVENT_LOG_CONSTRUCTION",
                evidence_ref="src/gymact/ocel.py:33-125",
                evidence_kind="source-contract",
                standing="ALIVE",
            ),
        ),
    ),
    ComponentCapabilities(
        component_ref="gymact.ocel.validate_ocel_log+write_ocel_log",
        capabilities=(
            CapabilityEvidence(
                capability_id="OCEL_EMISSION",
                evidence_ref="src/gymact/ocel.py:33-160",
                evidence_kind="source-contract",
                standing="ALIVE",
            ),
        ),
    ),
    ComponentCapabilities(
        # Real, evidenced authority resolver: admits/refuses using real,
        # already-declared odrl:Permission facts in a pack's ontology graph, a
        # different evidence source than AllowListAuthorityResolver's Python-side
        # config but the same capability (a live authority gate). Found
        # uncataloged by the Court A inventory scan, added 2026-08-14.
        component_ref="gymact.gyms.ontology_gym.OdrlAuthorityResolver",
        capabilities=(
            CapabilityEvidence(
                capability_id="AUTHORITY_GATE",
                evidence_ref="src/gymact/gyms/ontology_gym.py:447-500",
                evidence_kind="source-contract",
                standing="ALIVE",
            ),
        ),
    ),
    ComponentCapabilities(
        # Real, evidenced authority resolver: tiered admission (elevated_ref vs
        # standard_ref) over a fixed capability set, distinct evidence source from
        # both AllowListAuthorityResolver and OdrlAuthorityResolver above. Found
        # uncataloged by the Court A inventory scan, added 2026-08-14.
        component_ref="gymact.gyms.ontology_gym.TieredAuthorityResolver",
        capabilities=(
            CapabilityEvidence(
                capability_id="AUTHORITY_GATE",
                evidence_ref="src/gymact/gyms/ontology_gym.py:508-540",
                evidence_kind="source-contract",
                standing="ALIVE",
            ),
        ),
    ),
    ComponentCapabilities(
        component_ref="gymact.process.ConformanceChecker",
        capabilities=(
            CapabilityEvidence(
                capability_id="CONFORMANCE_REPLAY",
                evidence_ref="src/gymact/process.py:97-146",
                evidence_kind="source-contract",
                standing="ALIVE",
            ),
        ),
    ),
)


# Explicit, evidenced judgments about what kind of gap a capability represents
# if no component above supplies it. An entry here is what distinguishes
# ADAPT (orchestration-only residual) from CREATE_PROVIDER (genuine new
# physics) from BLOCKED_DISCOVERY (no entry at all — stays UNKNOWN).
KNOWN_CAPABILITY_CLASSIFICATIONS: tuple[CapabilityClassification, ...] = (
    CapabilityClassification(
        capability_id="HUMAN_ACCESS_TOGGLE",
        kind="orchestration",
        reason=(
            "Whether a human may inspect a generated artifact during a standing "
            "run is an experimental-control condition on the harness driving an "
            "episode, not a property of any Environment/Provider. It composes "
            "existing materialize/observe/verify calls under a controlled "
            "condition rather than requiring new environment physics."
        ),
    ),
    CapabilityClassification(
        capability_id="STANDING_DERIVATION_DIFF",
        kind="orchestration",
        reason=(
            "Comparing two standing derivations (human-access-allowed vs "
            "human-access-denied) is a diff over two runs of the existing "
            "kernel.verify()/OCEL pipeline, not a new capability the world "
            "itself must supply."
        ),
    ),
    CapabilityClassification(
        capability_id="UNAUTHORIZED_PATH_PREDICATE",
        kind="orchestration",
        reason=(
            "A SPARQL ASK/SELECT gate over an admitted effect graph is exactly "
            "the pattern already proven by ggen/*-pack/gates/*.rq "
            "(scripts/run_sparql_gates.py) — projecting a predicate over "
            "existing evidence, not new world physics."
        ),
    ),
    CapabilityClassification(
        capability_id="COUNTERFACTUAL_PAIR_BINDING",
        kind="orchestration",
        reason=(
            "Binding two receipts/episodes together as a counterfactual pair is "
            "bookkeeping over the existing Receipt/EvidenceRecord chain "
            "(gymact.models.Receipt, gymact.evidence), not a new environment "
            "capability."
        ),
    ),
)


def known_component_inventory() -> tuple[ComponentCapabilities, ...]:
    """Return the hand-authored, evidenced component table."""
    return KNOWN_COMPONENT_CAPABILITIES


def known_capability_classifications() -> tuple[CapabilityClassification, ...]:
    """Return the hand-authored, evidenced classification table."""
    return KNOWN_CAPABILITY_CLASSIFICATIONS
