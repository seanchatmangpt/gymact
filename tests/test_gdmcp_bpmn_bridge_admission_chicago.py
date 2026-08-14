"""Court B instance for GDMCP_BPMN_REPLAY. Real CapabilityContract, real
compute_residual against the real, current inventory/classification tables
-- no mocks. Proves the gdmcp<->BPMN bridge stays ADAPT (composing two
already-real pieces), not CREATE_PROVIDER -- distinct from
BPMN_WORKFLOW_EXECUTION's own correct CREATE_PROVIDER verdict.
"""

from __future__ import annotations

from gymact.composition import CapabilityContract, compute_residual
from gymact.composition_inventory import (
    known_capability_classifications,
    known_component_inventory,
)


def test_gdmcp_bpmn_replay_resolves_to_adapt():
    contract = CapabilityContract(
        name="GdmcpBpmnReplay",
        required_capabilities=frozenset({"BPMN_WORKFLOW_EXECUTION", "GDMCP_BPMN_REPLAY"}),
    )
    decision = compute_residual(
        contract, known_component_inventory(), known_capability_classifications()
    )

    assert decision.decision == "ADAPT"
    assert decision.physics_residual == frozenset()
    assert decision.unclassified_residual == frozenset()
    assert decision.orchestration_residual == frozenset({"GDMCP_BPMN_REPLAY"})
