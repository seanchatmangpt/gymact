"""Court B instance for POWL_ADMITTED_GRAPH_REPLAY. Real CapabilityContract,
real compute_residual against the real, current inventory/classification
tables -- no mocks. Proves the POWL<->kernel bridge stays ADAPT (composing
two already-real pieces), the POWL-native sibling of
tests/test_gdmcp_bpmn_bridge_admission_chicago.py's own GDMCP_BPMN_REPLAY
verdict.
"""

from __future__ import annotations

from gymact.composition import CapabilityContract, compute_residual
from gymact.composition_inventory import (
    known_capability_classifications,
    known_component_inventory,
)


def test_powl_admitted_graph_replay_resolves_to_adapt():
    contract = CapabilityContract(
        name="PowlAdmittedGraphReplay",
        required_capabilities=frozenset({"POWL_ADMITTED_GRAPH_REPLAY"}),
    )
    decision = compute_residual(
        contract, known_component_inventory(), known_capability_classifications()
    )

    assert decision.decision == "ADAPT"
    assert decision.physics_residual == frozenset()
    assert decision.unclassified_residual == frozenset()
    assert decision.orchestration_residual == frozenset({"POWL_ADMITTED_GRAPH_REPLAY"})
