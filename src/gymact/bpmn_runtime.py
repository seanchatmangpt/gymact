"""Real BPMN 2.0 execution via SpiffWorkflow -- the real engine behind the
previously-inert `ProjectionKind.BPMN` path.

Before this module: `"bpmn"` existed throughout gymact only as a symbolic
tag (`TransportKind.BPMN`, `ProviderFamily.BPMN`, `ProjectionKind.BPMN`) and
`gymact.lab.project_action()`'s BPMN branch produced an inert payload dict
(`{"element": "serviceTask", "implementation": "gymact-intent"}`) that
nothing ever executed. `SpiffWorkflow` itself was named only aspirationally
in `.claude/rules/python-native.md`'s dependency table -- not installed, not
imported anywhere real.

This module composes with, and does not replace, any existing gymact
process abstraction: `gymact.process.LIFECYCLE` (the kernel's own 8-op
Operation FSM), `gymact.powl.*` (partial-order workflow algebra/executor),
`gymact.epistemic_process_kernel` (DSPy-driven epistemic reasoning loop),
and `gymact.mcp_process_control` (deterministic MCP-call dispatch graph) are
all real, distinct, unrelated scopes -- none of them model BPMN 2.0
token/place-transition execution semantics, which is what SpiffWorkflow
genuinely, independently supplies. Per this session's composition-admission
discipline (`gymact.composition`), `BPMN_WORKFLOW_EXECUTION` is classified
`world_physics`, not `orchestration` -- unlike most of this session's other
additions, the correct move here really is "depend on a real, independent
engine," not "compose existing gymact components."

This module is a thin adapter: real `SpiffWorkflow.bpmn.parser.BpmnParser`
parses a real `.bpmn` file, a real `SpiffWorkflow.bpmn.workflow.BpmnWorkflow`
executes it (`run_all()`), and the result is projected into a small,
gymact-typed `BpmnWorkflowResult` -- no synthetic task history, no stubbed
engine.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from SpiffWorkflow.bpmn.parser import BpmnParser
from SpiffWorkflow.bpmn.workflow import BpmnWorkflow
from SpiffWorkflow.task import TaskState

from gymact.models import FrozenModel

__all__ = ["BpmnWorkflowResult", "BpmnWorkflowRefusal", "run_bpmn_workflow"]


class BpmnWorkflowRefusal(RuntimeError):
    """Raised for a real, named failure -- a missing/unparsable `.bpmn`
    file, or an unknown `process_id` -- never a silent empty result."""


class BpmnWorkflowResult(FrozenModel):
    """Real, typed outcome of one SpiffWorkflow BPMN run."""

    process_id: str
    completed_task_names: tuple[str, ...]
    is_completed: bool
    final_data: dict[str, Any]


def run_bpmn_workflow(
    bpmn_path: str | Path,
    process_id: str,
    *,
    initial_data: dict[str, Any] | None = None,
) -> BpmnWorkflowResult:
    """Real parse + real run of a real `.bpmn` file's named process.

    Raises `BpmnWorkflowRefusal` if the file is missing/unparsable or the
    `process_id` isn't defined in it -- both real, SpiffWorkflow-raised
    conditions, wrapped with a stable gymact-facing error type rather than
    leaking SpiffWorkflow's own exception hierarchy directly."""
    path = Path(bpmn_path)
    if not path.is_file():
        raise BpmnWorkflowRefusal(f"REFUSED:BPMN_FILE_MISSING:{path}")

    parser = BpmnParser()
    try:
        parser.add_bpmn_file(str(path))
        spec = parser.get_spec(process_id)
    except Exception as exc:  # SpiffWorkflow's own parse/lookup errors
        raise BpmnWorkflowRefusal(
            f"REFUSED:BPMN_PARSE_OR_SPEC_LOOKUP_FAILED:process_id={process_id!r}:{exc}"
        ) from exc

    workflow = BpmnWorkflow(spec)
    if initial_data:
        workflow.set_data(**initial_data)

    workflow.run_all()

    completed_task_names = tuple(
        task.task_spec.name
        for task in workflow.get_tasks()
        if task.state == TaskState.COMPLETED
    )

    return BpmnWorkflowResult(
        process_id=process_id,
        completed_task_names=completed_task_names,
        is_completed=workflow.is_completed(),
        final_data=dict(workflow.data),
    )
