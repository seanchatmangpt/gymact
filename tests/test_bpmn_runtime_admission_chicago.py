"""Court B instance for BPMN_WORKFLOW_EXECUTION -- the contrast case to this
session's other additions. Real CapabilityContract, real compute_residual
against the real, current inventory/classification tables -- no mocks.

Lifecycle note, stated honestly rather than left implicit: when
`BPMN_WORKFLOW_EXECUTION` was first classified `world_physics`, no
component supplied it yet, so `compute_residual` correctly authorized
`CREATE_PROVIDER` -- that authorization is what `gymact.bpmn_runtime` (this
session's real SpiffWorkflow wrapper) was built against. Now that it's real
and catalogued (`ComponentCapabilities(component_ref="gymact.bpmn_runtime
.run_bpmn_workflow", ...)`), the SAME capability id correctly resolves to
`REUSE` for any new contract asking for it -- this is the intended,
honest lifecycle (`CREATE_PROVIDER` -> built -> `REUSE`), not a regression
of the earlier finding. `test_gdmcp_bpmn_bridge_admission_chicago.py`
exercises the now-`REUSE`-able capability composed with a real orchestration
layer (`ADAPT`).
"""

from __future__ import annotations

from gymact.composition import CapabilityClassification, CapabilityContract, compute_residual
from gymact.composition_inventory import (
    known_capability_classifications,
    known_component_inventory,
)


def test_bpmn_workflow_execution_now_resolves_to_reuse():
    """gymact.bpmn_runtime.run_bpmn_workflow is real and catalogued; a
    contract asking only for BPMN_WORKFLOW_EXECUTION now resolves to REUSE,
    not CREATE_PROVIDER -- proving the gate correctly reflects that the
    physics gap it once authorized creating has since been closed."""
    contract = CapabilityContract(
        name="BpmnWorkflowExecution",
        required_capabilities=frozenset({"BPMN_WORKFLOW_EXECUTION"}),
    )
    decision = compute_residual(
        contract, known_component_inventory(), known_capability_classifications()
    )

    assert decision.decision == "REUSE"
    assert decision.residual_requirements == frozenset()
    assert decision.selected_components == ("gymact.bpmn_runtime.run_bpmn_workflow",)


def test_a_genuinely_unsupplied_physics_capability_still_authorizes_create_provider():
    """The gate must still reach CREATE_PROVIDER for a real, still-open
    physics gap -- proving REUSE above isn't because the gate stopped being
    able to say CREATE_PROVIDER at all. Uses a local, ad-hoc classification
    (not added to the real repo tables) for a capability nothing supplies,
    mirroring the same falsifiability pattern this session's other
    admission tests already established."""
    contract = CapabilityContract(
        name="StillOpenPhysicsGap",
        required_capabilities=frozenset({"DISTRIBUTED_TRACING_CORRELATION_ENGINE"}),
    )
    local_classifications = known_capability_classifications() + (
        CapabilityClassification(
            capability_id="DISTRIBUTED_TRACING_CORRELATION_ENGINE",
            kind="world_physics",
            reason="test fixture: no known component supplies this and none should.",
        ),
    )

    decision = compute_residual(contract, known_component_inventory(), local_classifications)

    assert decision.decision == "CREATE_PROVIDER"
    assert decision.physics_residual == frozenset({"DISTRIBUTED_TRACING_CORRELATION_ENGINE"})
