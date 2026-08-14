"""Connects `gdmcp` (deterministic MCP program compilation) to
`gymact.bpmn_runtime`'s real SpiffWorkflow engine -- BPMN as the real
scheduler for a `CompiledGdmcpProgram`'s already-rendered
`ActuationIntent`s.

Real, safe-dispatch pattern followed here, studied directly from
`~/autotel`'s working code before designing (not reinvented blind):
`~/autotel/autotel/workflows/dspy_bpmn_parser.py`'s `DspyServiceTask
._run_hook` resolves a **name** parsed from the BPMN XML through a closed,
explicitly-populated registry -- never `eval`/`exec`/`getattr`-by-string.
This module follows the same principle using SpiffWorkflow's own real,
built-in mechanism for it (newer than what autotel's version used):
`SpiffWorkflow.spiff.parser.SpiffBpmnParser` natively parses the
`spiffworkflow:serviceTaskOperator` XML extension into an `operation_name`,
and a custom `PythonScriptEngine.call_service(task, operation_name,
operation_params)` override is the real, official hook SpiffWorkflow itself
provides for resolving that name -- no parser/task-spec subclassing needed.

The generated BPMN carries only an **integer step index** per
`serviceTask`, never a capability IRI, payload, or authority ref -- those
values never appear in the XML at all. The custom script engine below does
not call `kernel.act()` itself (SpiffWorkflow's `call_service` hook is
synchronous; `kernel.act()` is real, async GymAct kernel code) -- it only
*records* the real, observed fire order. `replay_compiled_program_via_bpmn`
then drives the real, sequential `kernel.act()` calls from that real order,
in ordinary async Python -- BPMN determines scheduling, `kernel.act()`
remains the only real actuation path, `CapabilityScope`/`AuthorityResolver`
unchanged.
"""

from __future__ import annotations

import json

from SpiffWorkflow.bpmn.script_engine import PythonScriptEngine
from SpiffWorkflow.bpmn.workflow import BpmnWorkflow
from SpiffWorkflow.spiff.parser import SpiffBpmnParser

from gymact.gdmcp import CompiledGdmcpProgram
from gymact.kernel import GymAct
from gymact.models import ActuationResult

__all__ = ["BpmnReplayRefusal", "compile_program_to_bpmn", "replay_compiled_program_via_bpmn"]

_SPIFFWORKFLOW_NS = "http://spiffworkflow.org/bpmn/schema/1.0/core"
_BPMN_NS = "http://www.omg.org/spec/BPMN/20100524/MODEL"


class BpmnReplayRefusal(RuntimeError):
    """Raised for a real, named failure -- an empty program, a fire order
    that doesn't match the program's real step count, or a step recorded
    out of range. Never a silent partial replay."""


def compile_program_to_bpmn(program: CompiledGdmcpProgram) -> str:
    """Real, generated linear BPMN XML: one `serviceTask` per real
    `program.intents[i]`, each carrying only its own integer index as the
    `spiffworkflow:serviceTaskOperator`'s `id` (SpiffWorkflow's own real
    `operation_name` field, per `SpiffTaskParser._parse_servicetask_operator`
    -- `name = node.attrib['id']`). No capability IRI, payload, or
    authority value is ever written into this XML."""
    if not program.intents:
        raise BpmnReplayRefusal("REFUSED:EMPTY_PROGRAM")

    n = len(program.intents)
    nodes: list[str] = []
    flows: list[str] = []

    nodes.append('<bpmn:startEvent id="StartEvent_1"><bpmn:outgoing>Flow_0</bpmn:outgoing></bpmn:startEvent>')
    flows_source = "StartEvent_1"
    for i in range(n):
        task_id = f"Task_step_{i}"
        in_flow = f"Flow_{i}"
        out_flow = f"Flow_{i + 1}"
        nodes.append(
            f'<bpmn:serviceTask id="{task_id}" name="Step {i}">'
            f'<bpmn:extensionElements>'
            f'<spiffworkflow:serviceTaskOperator id="{i}" resultVariable="step_{i}_result">'
            f'<spiffworkflow:parameters/>'
            f'</spiffworkflow:serviceTaskOperator>'
            f'</bpmn:extensionElements>'
            f'<bpmn:incoming>{in_flow}</bpmn:incoming>'
            f'<bpmn:outgoing>{out_flow}</bpmn:outgoing>'
            f'</bpmn:serviceTask>'
        )
        flows.append(f'<bpmn:sequenceFlow id="{in_flow}" sourceRef="{flows_source}" targetRef="{task_id}"/>')
        flows_source = task_id
    nodes.append(f'<bpmn:endEvent id="EndEvent_1"><bpmn:incoming>Flow_{n}</bpmn:incoming></bpmn:endEvent>')
    flows.append(f'<bpmn:sequenceFlow id="Flow_{n}" sourceRef="{flows_source}" targetRef="EndEvent_1"/>')

    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f'<bpmn:definitions xmlns:bpmn="{_BPMN_NS}" '
        'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
        f'xmlns:spiffworkflow="{_SPIFFWORKFLOW_NS}" '
        f'id="Definitions_gdmcp_{program.program_digest[7:15]}" '
        'targetNamespace="urn:gymact:bpmn:gdmcp">'
        f'<bpmn:process id="gdmcp_{program.problem_id}" name="gdmcp {program.problem_id}" isExecutable="true">'
        + "".join(nodes)
        + "".join(flows)
        + "</bpmn:process></bpmn:definitions>"
    )


class _RecordingScriptEngine(PythonScriptEngine):
    """Real SpiffWorkflow script engine override. `call_service` is
    SpiffWorkflow's own official extension hook (see
    `SpiffWorkflow/spiff/specs/mixins/service_task.py`'s `ServiceTask
    ._execute`) -- this override does not eval/exec anything; it only
    appends the real, parsed integer `operation_name` to a real, ordered
    list, then returns a real, valid JSON result string (SpiffWorkflow's
    `ServiceTask._execute` calls `json.loads(result)` on the return value)."""

    def __init__(self) -> None:
        super().__init__()
        self.fire_order: list[int] = []

    def call_service(self, task: object, **kwargs: object) -> str:
        del task
        self.fire_order.append(int(kwargs["operation_name"]))  # type: ignore[arg-type]
        return json.dumps({"recorded": True})


def _real_fire_order(program: CompiledGdmcpProgram) -> tuple[int, ...]:
    """Real SpiffWorkflow parse + run of the real generated BPMN. Returns
    the real, observed step-index fire order -- no kernel call happens in
    this function."""
    bpmn_xml = compile_program_to_bpmn(program)
    parser = SpiffBpmnParser()
    # lxml.etree.fromstring refuses a unicode str carrying an XML encoding
    # declaration (real, confirmed error); BpmnParser.add_bpmn_str passes
    # its argument straight through to fromstring, so real bytes are
    # required here, not a real API choice this module gets to skip.
    parser.add_bpmn_str(bpmn_xml.encode("utf-8"), filename=f"gdmcp-{program.problem_id}.bpmn")
    spec = parser.get_spec(f"gdmcp_{program.problem_id}")

    engine = _RecordingScriptEngine()
    workflow = BpmnWorkflow(spec, script_engine=engine)
    workflow.run_all()

    if not workflow.is_completed():
        raise BpmnReplayRefusal(f"REFUSED:BPMN_DID_NOT_COMPLETE:problem_id={program.problem_id}")
    return tuple(engine.fire_order)


async def replay_compiled_program_via_bpmn(
    kernel: GymAct,
    program: CompiledGdmcpProgram,
) -> tuple[ActuationResult, ...]:
    """Real, two-phase replay. Phase 1 (sync): the real generated BPMN runs
    through real SpiffWorkflow and yields the real fire order -- no
    `kernel.act()` call happens here. Phase 2 (async): that real order
    drives real, sequential `kernel.act(program.intents[i])` calls -- the
    only real actuation path, `CapabilityScope`/`AuthorityResolver`
    unchanged, exactly as every other real call to `kernel.act()` in this
    codebase. Raises `BpmnReplayRefusal` if the real fire order doesn't
    exactly match the program's real step indices -- never a silent
    partial or reordered replay."""
    fire_order = _real_fire_order(program)
    expected = tuple(range(len(program.intents)))
    if fire_order != expected:
        raise BpmnReplayRefusal(
            f"REFUSED:FIRE_ORDER_MISMATCH:expected={expected!r},observed={fire_order!r}"
        )

    results: list[ActuationResult] = []
    for index in fire_order:
        result = await kernel.act(program.intents[index])
        results.append(result)
    return tuple(results)
