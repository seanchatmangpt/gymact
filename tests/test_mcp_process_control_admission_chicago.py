"""Court B instance for the deterministic-MCP-dispatch capability contract
(`gymact.mcp_process_control`). Real `CapabilityContract`, real
`compute_residual` against the real, current inventory/classification
tables -- no mocks. Proves this slice's own admission (`ADAPT`, not
`CREATE_PROVIDER`, not `COMPOSE`) before the dispatch code is exercised in
`tests/test_mcp_process_control_chicago.py`, the same discipline CROWN_P1
was gated by in `test_composition_admission_chicago.py`.
"""

from __future__ import annotations

from gymact.composition import CapabilityContract, compute_residual
from gymact.composition_inventory import (
    known_capability_classifications,
    known_component_inventory,
)

MCP_DISPATCH_REQUIRED = frozenset(
    {
        "AUTHORITY_GATE",
        "CAPABILITY_SCOPE_GATE",
        "CONFORMANCE_REPLAY",
        "DETERMINISTIC_MCP_DISPATCH",
        "PROCESS_MODEL_CONFORMANCE_GATE",
    }
)


def test_deterministic_mcp_dispatch_resolves_to_adapt():
    """The world-physics requirements (AUTHORITY_GATE, CAPABILITY_SCOPE_GATE,
    CONFORMANCE_REPLAY) are already covered by real components; the two
    orchestration-only requirements this session added
    (DETERMINISTIC_MCP_DISPATCH, PROCESS_MODEL_CONFORMANCE_GATE) resolve via
    their real classification entries. The honest mechanical result is
    ADAPT -- not CREATE_PROVIDER, and not COMPOSE (which would falsely claim
    a zero residual)."""
    contract = CapabilityContract(
        name="DeterministicMcpDispatch", required_capabilities=MCP_DISPATCH_REQUIRED
    )
    inventory = known_component_inventory()
    classifications = known_capability_classifications()

    decision = compute_residual(contract, inventory, classifications)

    assert decision.decision == "ADAPT"
    assert decision.physics_residual == frozenset()
    assert decision.unclassified_residual == frozenset()
    assert decision.orchestration_residual == frozenset(
        {"DETERMINISTIC_MCP_DISPATCH", "PROCESS_MODEL_CONFORMANCE_GATE"}
    )
    # Real, already-ALIVE components actually selected for the covered part.
    assert decision.covered_requirements == frozenset(
        {"AUTHORITY_GATE", "CAPABILITY_SCOPE_GATE", "CONFORMANCE_REPLAY"}
    )
    assert "gymact.process.ConformanceChecker" in decision.selected_components


def test_process_model_discovery_remains_blocked_discovery():
    """The deliberately-omitted mining/discovery half of the concept
    (turning OCEL logs into a process model, the wasm4pm_bridge.py-shaped
    capability) must resolve to BLOCKED_DISCOVERY -- proving the session's
    scoping decision (dispatch only, no discovery) is enforced by the gate
    itself, not just stated in prose."""
    contract = CapabilityContract(
        name="OcelDrivenProcessModelDiscovery",
        required_capabilities=frozenset({"PROCESS_MODEL_DISCOVERY"}),
    )
    inventory = known_component_inventory()
    classifications = known_capability_classifications()

    decision = compute_residual(contract, inventory, classifications)

    assert decision.decision == "BLOCKED_DISCOVERY"
    assert decision.unclassified_residual == frozenset({"PROCESS_MODEL_DISCOVERY"})
