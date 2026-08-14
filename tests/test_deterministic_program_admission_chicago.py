"""Court B instance for the provider-agnostic deterministic-program
compilation capability contract (`gymact.deterministic_program`). Real
`CapabilityContract`, real `compute_residual` against the real, current
inventory/classification tables -- no mocks. Proves this slice's own
admission (`ADAPT`) before `tests/test_deterministic_program_chicago.py`
exercises the real compile/run code.
"""

from __future__ import annotations

from gymact.composition import CapabilityContract, compute_residual
from gymact.composition_inventory import (
    known_capability_classifications,
    known_component_inventory,
)

DETERMINISTIC_PROGRAM_REQUIRED = frozenset(
    {
        "AUTHORITY_GATE",
        "CAPABILITY_SCOPE_GATE",
        "CONFORMANCE_REPLAY",
        "DETERMINISTIC_MCP_DISPATCH",
        "PROCESS_MODEL_CONFORMANCE_GATE",
        "DETERMINISTIC_PROGRAM_COMPILATION",
    }
)


def test_deterministic_program_compilation_resolves_to_adapt():
    """World-physics requirements are already covered by real components;
    the three orchestration-only requirements (DETERMINISTIC_MCP_DISPATCH,
    PROCESS_MODEL_CONFORMANCE_GATE, DETERMINISTIC_PROGRAM_COMPILATION)
    resolve via their real classification entries. ADAPT, not
    CREATE_PROVIDER, not COMPOSE."""
    contract = CapabilityContract(
        name="DeterministicProgramCompilation",
        required_capabilities=DETERMINISTIC_PROGRAM_REQUIRED,
    )
    decision = compute_residual(
        contract, known_component_inventory(), known_capability_classifications()
    )

    assert decision.decision == "ADAPT"
    assert decision.physics_residual == frozenset()
    assert decision.unclassified_residual == frozenset()
    assert decision.orchestration_residual == frozenset(
        {
            "DETERMINISTIC_MCP_DISPATCH",
            "PROCESS_MODEL_CONFORMANCE_GATE",
            "DETERMINISTIC_PROGRAM_COMPILATION",
        }
    )
    assert "gymact.process.ConformanceChecker" in decision.selected_components


def test_process_model_discovery_stays_blocked_after_this_addition_too():
    """Generalizing dispatch into per-provider program compilation must not
    quietly reopen the deliberately-excluded OCEL-mining/discovery gap."""
    contract = CapabilityContract(
        name="ProcessModelDiscoveryStillBlocked",
        required_capabilities=frozenset({"PROCESS_MODEL_DISCOVERY"}),
    )
    decision = compute_residual(
        contract, known_component_inventory(), known_capability_classifications()
    )
    assert decision.decision == "BLOCKED_DISCOVERY"
