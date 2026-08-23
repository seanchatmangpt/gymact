from __future__ import annotations

import pytest

from gymact.harness_science import (
    ConfigurationEffect,
    ControlPreservation,
    EvolutionEvaluation,
    ExperimentSubject,
    HarnessBenchRun,
    HarnessChangeHypothesis,
    HarnessConfiguration,
    HarnessScienceSnapshot,
    HypothesisDirection,
    HypothesisStanding,
    LifecycleCaseResult,
    LifecyclePhase,
    PairedOutcome,
    ProcessDefectCategory,
    ProcessFinding,
    ProcessScorecard,
    SafetyArtifact,
    SafetyDiagnosis,
    TrajectoryEvent,
    TreatmentAxis,
    admit_controlled_pair,
    admit_harness_change,
    admit_safety_evolution,
    audit_harness_safety,
    audit_trajectory,
    evaluate_hypothesis,
    lifecycle_scorecard,
    measure_configuration_effect,
    replay_snapshot,
)


def subject(**changes: str) -> ExperimentSubject:
    data = {
        "benchmark_id": "bench",
        "harness_digest": "h1",
        "environment_id": "env",
        "agent_id": "agent",
        "model_id": "model",
    }
    data.update(changes)
    return ExperimentSubject(**data)


def test_harness_configuration_has_deterministic_identity():
    config = HarnessConfiguration(
        system_prompt_ref="sp",
        toolset_ref="tools",
        context_policy_ref="context",
        memory_ref="memory",
        planning_ref="plan",
        recovery_ref="recovery",
    )
    assert config.digest == config.model_copy().digest


def test_controlled_pair_admits_exactly_one_declared_axis():
    admission = admit_controlled_pair(
        subject(), subject(harness_digest="h2"), TreatmentAxis.HARNESS
    )
    assert admission.accepted
    assert admission.changed_axes == (TreatmentAxis.HARNESS,)


def test_controlled_pair_refuses_hidden_environment_confounder():
    admission = admit_controlled_pair(
        subject(),
        subject(harness_digest="h2", environment_id="env2"),
        TreatmentAxis.HARNESS,
    )
    assert not admission.accepted
    assert admission.reason == "REFUSED[CONFOUNDED_TREATMENT]"


def test_controlled_pair_refuses_vacuous_treatment():
    admission = admit_controlled_pair(subject(), subject(), TreatmentAxis.HARNESS)
    assert not admission.accepted
    assert admission.reason == "REFUSED[NO_TREATMENT_CHANGE]"


def test_harness_bench_binds_capability_to_model_harness_configuration():
    run = HarnessBenchRun(
        subject=subject(model_id="model-x", harness_digest="harness-y"),
        completion=True,
        process_quality=0.8,
        efficiency=0.75,
        failure_count=1,
        evidence_refs=("urn:evidence:harness-bench",),
    )
    assert run.configuration_key == "model-x@harness-y"
    assert run.process_quality == 0.8


def test_configuration_effect_preserves_budget_and_held_out_dimensions():
    admission = admit_controlled_pair(
        subject(), subject(harness_digest="h2"), TreatmentAxis.HARNESS
    )
    outcome = PairedOutcome(
        control_score=0.6,
        treatment_score=0.7,
        budget_control=100,
        budget_treatment=120,
        held_out=True,
        evidence_refs=("urn:evidence:pair",),
    )
    effect = measure_configuration_effect(admission, outcome)
    assert effect.delta == pytest.approx(0.1)
    assert effect.budget_delta == 20
    assert effect.held_out


def test_harness_change_requires_reversible_task_agnostic_grounded_feedback():
    hypothesis = HarnessChangeHypothesis(
        change_id="change-1",
        component_ref="tools/policy",
        prediction="improve control",
        expected_direction=HypothesisDirection.IMPROVE,
        falsifier="control does not improve",
        evidence_refs=("urn:evidence:trajectory",),
    )
    assert admit_harness_change(
        hypothesis,
        task_agnostic=True,
        proactive_feedback_refs=("urn:evidence:agent-feedback",),
    ).accepted
    refused = admit_harness_change(
        hypothesis,
        task_agnostic=False,
        proactive_feedback_refs=("urn:evidence:agent-feedback",),
    )
    assert refused.reason == "REFUSED[TASK_SPECIFIC_HARNESS_OVERFIT]"


def test_evolution_claim_requires_matched_budget_and_can_report_generalization():
    evaluation = EvolutionEvaluation(
        evolved_score=0.8,
        simple_search_score=0.75,
        evolved_budget=10,
        simple_search_budget=10,
        held_out_score=0.02,
    )
    assert evaluation.matched_budget
    assert evaluation.beats_simple_search
    assert evaluation.generalizes is True


def test_ahe_hypothesis_is_falsifiable_not_trial_and_error():
    hypothesis = HarnessChangeHypothesis(
        change_id="change-1",
        component_ref="tools/policy",
        prediction="reduce process failures",
        expected_direction=HypothesisDirection.IMPROVE,
        falsifier="held-out score does not improve",
        evidence_refs=("urn:evidence:diagnosis",),
    )
    effect = ConfigurationEffect(
        axis=TreatmentAxis.HARNESS,
        delta=-0.05,
        budget_delta=0,
        held_out=True,
        evidence_refs=("urn:evidence:rollout",),
    )
    result = evaluate_hypothesis(hypothesis, effect)
    assert result.standing == HypothesisStanding.FALSIFIED
    assert result.reason == "FALSIFIER_TRIGGERED"


def test_hypothesis_cannot_be_supported_without_evidence_ancestry():
    hypothesis = HarnessChangeHypothesis(
        change_id="change-1",
        component_ref="middleware",
        prediction="improve score",
        expected_direction=HypothesisDirection.IMPROVE,
        falsifier="score does not improve",
    )
    effect = ConfigurationEffect(
        axis=TreatmentAxis.HARNESS,
        delta=0.2,
        budget_delta=0,
        held_out=True,
        evidence_refs=("urn:evidence:rollout",),
    )
    assert evaluate_hypothesis(hypothesis, effect).standing == HypothesisStanding.INCONCLUSIVE


def test_procctrl_solved_task_can_still_fail_process_quality():
    scorecard = ProcessScorecard(
        task_solved=True,
        findings=(
            ProcessFinding(
                defect_type="verification-omission",
                category=ProcessDefectCategory.WORKFLOW_ARCHITECTURE,
                severity=4,
                evidence_ref="urn:trace:42",
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
    assert scorecard.task_solved
    assert not scorecard.process_qualified


def test_control_preservation_keeps_five_dimensions_noncollapsed():
    control = ControlPreservation(
        interpretable=True,
        interruptible=True,
        correctable=False,
        reversible=True,
        returns_authority=True,
    )
    assert control.score == pytest.approx(0.8)


def test_trajectory_safety_failure_survives_endpoint_success():
    audit = audit_trajectory(
        (
            TrajectoryEvent(
                sequence=1,
                event_ref="event-1",
                safe=True,
                control_preserved=True,
                evidence_ref="urn:event:1",
            ),
            TrajectoryEvent(
                sequence=2,
                event_ref="event-2",
                safe=False,
                control_preserved=True,
                evidence_ref="urn:event:2",
            ),
        ),
        task_solved=True,
    )
    assert audit.task_solved
    assert not audit.safe
    assert audit.first_failure_ref == "event-2"


def test_trajectory_refuses_duplicate_sequence_identity():
    event = TrajectoryEvent(
        sequence=1,
        event_ref="event-1",
        safe=True,
        control_preserved=True,
        evidence_ref="urn:event:1",
    )
    with pytest.raises(ValueError, match="DUPLICATE_TRAJECTORY_SEQUENCE"):
        audit_trajectory(
            (event, event.model_copy(update={"event_ref": "event-2"})), task_solved=True
        )


def test_harness_audit_requires_all_three_safety_layers_and_hidden_evidence():
    audit = audit_harness_safety(
        boundary_compliance=True,
        execution_fidelity=True,
        system_stability=False,
        hidden_evidence_refs=("urn:hidden:audit:1",),
        perturbation_ref="urn:stressor:runtime-error",
    )
    assert not audit.safe
    with pytest.raises(ValueError, match="AGENT_INDEPENDENT_AUDIT_EVIDENCE"):
        audit_harness_safety(
            boundary_compliance=True,
            execution_fidelity=True,
            system_stability=True,
            hidden_evidence_refs=(),
        )


def test_she_candidate_requires_safety_gain_utility_and_held_out_evidence():
    diagnosis = SafetyDiagnosis(
        artifact=SafetyArtifact.TOOL_POLICY,
        trajectory_ref="urn:trajectory:1",
        failure="unsafe tool authorization",
        evidence_refs=("urn:evidence:failure",),
    )
    decision = admit_safety_evolution(
        diagnosis,
        baseline_attack_success=0.4,
        candidate_attack_success=0.2,
        baseline_utility=0.8,
        candidate_utility=0.82,
        held_out=True,
    )
    assert decision.accepted


def test_she_refuses_safety_gain_that_costs_utility():
    diagnosis = SafetyDiagnosis(
        artifact=SafetyArtifact.RULE_BANK,
        trajectory_ref="urn:trajectory:1",
        failure="unsafe boundary",
        evidence_refs=("urn:evidence:failure",),
    )
    decision = admit_safety_evolution(
        diagnosis,
        baseline_attack_success=0.4,
        candidate_attack_success=0.2,
        baseline_utility=0.8,
        candidate_utility=0.6,
        held_out=True,
    )
    assert not decision.accepted


def test_harnessrisk_detection_does_not_cancel_attack_success():
    scorecard = lifecycle_scorecard(
        (
            LifecycleCaseResult(
                case_id="case-1",
                phase=LifecyclePhase.HARNESS_CONFIGURATION,
                utility=True,
                attack_success=True,
                persistence=True,
                detection=True,
                evidence_refs=("urn:risk:1",),
            ),
            LifecycleCaseResult(
                case_id="case-2",
                phase=LifecyclePhase.INCIDENT_RECOVERY,
                utility=True,
                attack_success=False,
                persistence=False,
                detection=True,
                evidence_refs=("urn:risk:2",),
            ),
        )
    )
    assert scorecard.utility == 1.0
    assert scorecard.attack_success_rate == 0.5
    assert scorecard.detection == 1.0
    assert scorecard.persistence == 0.5


def test_snapshot_replay_is_deterministic_and_not_an_actuation_receipt():
    snapshot = HarnessScienceSnapshot(subject=subject(), evidence_refs=("urn:evidence:1",))
    assert replay_snapshot(snapshot) == replay_snapshot(snapshot.model_copy())
    assert len(snapshot.fingerprint) == 64
