from __future__ import annotations

from rdflib import RDF

from gymact import harness_science_semantic as sem
from gymact.harness_science import (
    ConfigurationEffect,
    ControlPreservation,
    ExperimentSubject,
    HarnessScienceSnapshot,
    LifecycleCaseResult,
    LifecyclePhase,
    ProcessDefectCategory,
    ProcessFinding,
    ProcessScorecard,
    TrajectoryEvent,
    TreatmentAxis,
    audit_harness_safety,
    audit_trajectory,
    lifecycle_scorecard,
)


def test_configuration_effect_is_sosa_observation():
    effect = ConfigurationEffect(
        axis=TreatmentAxis.HARNESS,
        delta=0.1,
        budget_delta=0,
        held_out=True,
        evidence_refs=("urn:evidence:1",),
    )
    graph = sem.configuration_effect_graph(effect, run_iri="urn:run:effect")
    assert any(object_ref == sem.SOSA.Observation for _, _, object_ref in graph)


def test_process_findings_use_earl_and_public_evidence():
    scorecard = ProcessScorecard(
        task_solved=True,
        findings=(
            ProcessFinding(
                defect_type="verification-omission",
                category=ProcessDefectCategory.WORKFLOW_ARCHITECTURE,
                severity=3,
                evidence_ref="urn:evidence:process",
            ),
        ),
        control=ControlPreservation(
            interpretable=True,
            interruptible=True,
            correctable=True,
            reversible=True,
            returns_authority=True,
        ),
    )
    graph = sem.process_graph(scorecard, run_iri="urn:run:process")
    assert any(object_ref == sem.EARL.Assertion for _, _, object_ref in graph)


def test_harness_audit_projects_three_public_dqv_measurements():
    audit = audit_harness_safety(
        boundary_compliance=True,
        execution_fidelity=True,
        system_stability=True,
        hidden_evidence_refs=("urn:hidden:audit:1",),
    )
    graph = sem.harness_audit_graph(audit, run_iri="urn:run:audit")
    measurements = [
        node for node, _, object_ref in graph if object_ref == sem.DQV.QualityMeasurement
    ]
    assert len(measurements) == 3


def test_trajectory_and_lifecycle_project_dqv_measurements():
    trajectory = audit_trajectory(
        (
            TrajectoryEvent(
                sequence=0,
                event_ref="event-0",
                safe=True,
                control_preserved=True,
                evidence_ref="urn:evidence:event-0",
            ),
        ),
        task_solved=True,
    )
    lifecycle = lifecycle_scorecard(
        (
            LifecycleCaseResult(
                case_id="case-1",
                phase=LifecyclePhase.ACTION_CONTROL,
                utility=True,
                attack_success=False,
                persistence=False,
                detection=True,
                evidence_refs=("urn:evidence:risk",),
            ),
        )
    )
    trajectory_graph = sem.trajectory_graph(trajectory, run_iri="urn:run:trajectory")
    lifecycle_graph = sem.lifecycle_graph(lifecycle, run_iri="urn:run:lifecycle")
    assert any(object_ref == sem.DQV.QualityMeasurement for _, _, object_ref in trajectory_graph)
    assert any(object_ref == sem.DQV.QualityMeasurement for _, _, object_ref in lifecycle_graph)
    assert any(object_ref == sem.ODRL.Policy for _, _, object_ref in lifecycle_graph)


def test_snapshot_uses_prov_bundle_and_no_custom_class_tbox():
    snapshot = HarnessScienceSnapshot(
        subject=ExperimentSubject(
            benchmark_id="bench",
            harness_digest="harness",
            environment_id="env",
            agent_id="agent",
            model_id="model",
        ),
        evidence_refs=("urn:evidence:1",),
    )
    graph = sem.snapshot_graph(snapshot, run_iri="urn:run:snapshot")
    assert any(object_ref == sem.PROV.Bundle for _, _, object_ref in graph)
    assert not any(
        str(object_ref).startswith("urn:gymact:harness-science:class-")
        for _, predicate, object_ref in graph
        if predicate == RDF.type
    )
