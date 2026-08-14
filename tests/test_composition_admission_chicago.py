"""Chicago-style tests for the reuse-before-create composition-admission gate.

Real `CapabilityContract`/`ComponentCapabilities`/`CapabilityClassification`
models, real `compute_residual`/`assert_create_authorized` functions, real
hand-authored inventory and classification tables — no mocks, no
monkeypatching. Assertions are made directly on the real returned
`CompositionDecision`, matching the discipline already used by
`tests/test_registry_completeness_chicago.py` and `tests/test_ocel_standing.py`.

The load-bearing property under test: an unrecognized capability must resolve
to BLOCKED_DISCOVERY, never CREATE_PROVIDER — UNKNOWN must never silently
collapse into ABSENT.
"""

from __future__ import annotations

import pytest

from gymact.composition import (
    CapabilityClassification,
    CapabilityContract,
    CreateNotAuthorized,
    assert_create_authorized,
    compute_residual,
)
from gymact.composition_inventory import (
    known_capability_classifications,
    known_component_inventory,
)

# The requirement list for "CROWN_P1" (UnauthorizedActuationPath) as named in the
# design discussion this gate exists to check before any crown_gym.py is authored.
# The first 8 are supplied by existing components; the last 4 are experiment
# orchestration/wiring, explicitly classified (not inferred) as such in
# gymact.composition_inventory.KNOWN_CAPABILITY_CLASSIFICATIONS.
CROWN_P1_REQUIRED = frozenset(
    {
        "MATERIALIZE_ISOLATED_SUBJECT",
        "INDEPENDENT_WORLD_OBSERVATION",
        "CAPABILITY_SCOPE_GATE",
        "AUTHORITY_GATE",
        "INDEPENDENT_POSTCONDITION_JUDGMENT",
        "RECEIPTED_EFFECT_PORT",
        "OCEL_EMISSION",
        "CONFORMANCE_REPLAY",
        "HUMAN_ACCESS_TOGGLE",
        "STANDING_DERIVATION_DIFF",
        "UNAUTHORIZED_PATH_PREDICATE",
        "COUNTERFACTUAL_PAIR_BINDING",
    }
)


def test_crown_p1_resolves_to_adapt_not_reuse_compose_or_create():
    """CROWN_P1's world-physics requirements are fully covered by existing
    components; its remaining 4 requirements are explicitly classified as
    orchestration-only. The honest mechanical result is ADAPT: GymAct already
    has the physics, only composition/wiring is missing — not COMPOSE (that
    would falsely claim zero residual) and not CREATE_PROVIDER."""
    contract = CapabilityContract(name="UnauthorizedActuationPath", required_capabilities=CROWN_P1_REQUIRED)
    inventory = known_component_inventory()
    classifications = known_capability_classifications()

    decision = compute_residual(contract, inventory, classifications)

    assert decision.decision == "ADAPT"
    assert decision.physics_residual == frozenset()
    assert decision.unclassified_residual == frozenset()
    assert decision.orchestration_residual == frozenset(
        {
            "HUMAN_ACCESS_TOGGLE",
            "STANDING_DERIVATION_DIFF",
            "UNAUTHORIZED_PATH_PREDICATE",
            "COUNTERFACTUAL_PAIR_BINDING",
        }
    )
    # Real components actually selected for the covered part of the contract.
    assert "gymact.gyms.swegym.SWEGymProvider" in decision.selected_components
    assert "gymact.verification.PostconditionVerifier" in decision.selected_components


def test_create_provider_is_refused_for_crown_p1():
    """The enforcement half must raise for CROWN_P1 given current inventory and
    classifications — an ADAPT decision does not authorize CREATE_PROVIDER."""
    contract = CapabilityContract(name="UnauthorizedActuationPath", required_capabilities=CROWN_P1_REQUIRED)
    inventory = known_component_inventory()
    classifications = known_capability_classifications()

    with pytest.raises(CreateNotAuthorized) as excinfo:
        assert_create_authorized(contract, inventory, classifications)

    assert "UnauthorizedActuationPath" in str(excinfo.value)


def test_unrecognized_capability_blocks_discovery_never_creates():
    """A capability with no entry in EITHER the supply table or the
    classification table must resolve to BLOCKED_DISCOVERY, not
    CREATE_PROVIDER — proving UNKNOWN is never silently treated as ABSENT."""
    contract = CapabilityContract(
        name="SomeUnstudiedContract",
        required_capabilities=frozenset({"NEVER_BEFORE_NAMED_CAPABILITY"}),
    )
    inventory = known_component_inventory()
    classifications = known_capability_classifications()

    decision = compute_residual(contract, inventory, classifications)
    assert decision.decision == "BLOCKED_DISCOVERY"
    assert decision.unclassified_residual == frozenset({"NEVER_BEFORE_NAMED_CAPABILITY"})

    with pytest.raises(CreateNotAuthorized):
        assert_create_authorized(contract, inventory, classifications)


def test_create_provider_is_authorized_only_for_an_explicitly_classified_physics_gap():
    """CREATE_PROVIDER must actually be reachable — but only via an explicit,
    evidenced world_physics classification supplied by the caller, never
    inferred from mere absence."""
    contract = CapabilityContract(
        name="ExperimentalCrownFeature",
        required_capabilities=frozenset({"QUANTUM_RANDOM_ORACLE"}),
    )
    inventory = known_component_inventory()
    # Deliberately local, ad-hoc classification (not added to the real repo
    # table) to prove the mechanism works when a genuine physics gap IS named.
    local_classifications = (
        CapabilityClassification(
            capability_id="QUANTUM_RANDOM_ORACLE",
            kind="world_physics",
            reason="test fixture: no known component supplies this and none should.",
        ),
    )

    decision = compute_residual(contract, inventory, local_classifications)
    assert decision.decision == "CREATE_PROVIDER"
    assert decision.physics_residual == frozenset({"QUANTUM_RANDOM_ORACLE"})

    returned = assert_create_authorized(contract, inventory, local_classifications)
    assert returned.decision == "CREATE_PROVIDER"


def test_single_component_contract_resolves_to_reuse():
    """A contract fully covered by exactly one component's own capabilities
    must be REUSE, distinguishing it from the multi-component COMPOSE case."""
    contract = CapabilityContract(
        name="JustCapabilityScope",
        required_capabilities=frozenset({"CAPABILITY_SCOPE_GATE"}),
    )
    inventory = known_component_inventory()

    decision = compute_residual(contract, inventory)

    assert decision.decision == "REUSE"
    assert decision.selected_components == ("gymact.agent.AllowListCapabilityScope",)


def test_two_component_contract_resolves_to_compose():
    """A contract requiring capabilities each supplied by a different single
    component must be COMPOSE — no single component covers both."""
    contract = CapabilityContract(
        name="ScopeAndAuthority",
        required_capabilities=frozenset({"CAPABILITY_SCOPE_GATE", "FAIL_CLOSED_REFUSAL"}),
    )
    inventory = known_component_inventory()

    decision = compute_residual(contract, inventory)

    assert decision.decision == "COMPOSE"
    assert decision.residual_requirements == frozenset()
    assert set(decision.selected_components) == {
        "gymact.agent.AllowListCapabilityScope",
        "gymact.authority.DenyAuthorityResolver",
    }
