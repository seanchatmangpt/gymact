"""Chicago-style tests for `gymact.bpmn_runtime.run_bpmn_workflow`. Real
SpiffWorkflow parse + real execution against a real `.bpmn` fixture -- no
mocks anywhere. SpiffWorkflow itself does the parsing/execution; this
module only adapts its real result.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from gymact.bpmn_runtime import BpmnWorkflowRefusal, run_bpmn_workflow

FIXTURE = Path(__file__).parent / "fixtures" / "simple_sequential.bpmn"


def test_a_real_sequential_bpmn_process_runs_to_completion():
    result = run_bpmn_workflow(FIXTURE, "simple_sequential")

    assert result.is_completed is True
    assert result.process_id == "simple_sequential"
    assert "Task_A" in result.completed_task_names
    assert "Task_B" in result.completed_task_names
    assert result.completed_task_names.index("Task_A") < result.completed_task_names.index("Task_B")
    assert result.final_data == {"task_a_ran": True, "task_b_ran": True}


def test_missing_bpmn_file_is_refused_not_silently_empty():
    with pytest.raises(BpmnWorkflowRefusal, match="BPMN_FILE_MISSING"):
        run_bpmn_workflow(Path("tests/fixtures/does_not_exist.bpmn"), "simple_sequential")


def test_unknown_process_id_is_refused_not_silently_empty():
    with pytest.raises(BpmnWorkflowRefusal, match="BPMN_PARSE_OR_SPEC_LOOKUP_FAILED"):
        run_bpmn_workflow(FIXTURE, "no_such_process_id")
