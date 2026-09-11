from __future__ import annotations

import pytest

from gymact import harness_if as hif


def rule(
    rule_id: str,
    *,
    prior=hif.Prior.AGAINST,
    modality=hif.Modality.REQUIRE,
    severity=hif.Severity.MUST,
    surface=hif.Surface.PROJECT_FILE,
):
    return hif.Constraint(
        rule_id=rule_id,
        text=f"rule {rule_id}",
        family=hif.RuleFamily.WORKFLOW,
        modality=modality,
        prior=prior,
        prior_lineage=hif.PriorLineage.ZERO_INJECTION,
        observability=hif.Observability.BEHAVIORAL,
        verifiability=hif.Verifiability.DETERMINISTIC,
        universality=hif.Universality.CROSS_CODING,
        scoring_method=hif.ScoringMethod.COMMAND_OUTPUT,
        severity=severity,
        surface_fit={surface: hif.SurfaceFit.HIGH},
        surface_variants={surface: f"rendered {rule_id}"},
    )


def verdict(agent: str, item: str, rnd: int, rule_id: str, status, **kwargs):
    return hif.RuleVerdict(
        agent_id=agent,
        item_id=item,
        round_id=rnd,
        rule_id=rule_id,
        surface=hif.Surface.PROJECT_FILE,
        status=status,
        method=hif.ScoringMethod.COMMAND_OUTPUT,
        **kwargs,
    )


def test_surface_admission_is_fail_closed():
    item = rule("r1")
    assert hif.place_constraint(
        item, hif.Surface.PROJECT_FILE
    ).rendered_text == "rendered r1"
    with pytest.raises(ValueError, match="INADMISSIBLE_SURFACE"):
        hif.place_constraint(item, hif.Surface.TOOL_DESCRIPTION)
    with pytest.raises(ValueError, match="HD_IS_FIXED"):
        hif.place_constraint(item, hif.Surface.HARNESS_DEFAULT)


def test_zero_injection_requires_target_withheld_and_five_of_nine_consensus():
    probes = [
        hif.PriorProbe(
            rule_id="r1",
            build_id=f"m{i}",
            target_rule_withheld=True,
            observed_prior=hif.Prior.AGAINST if i < 5 else hif.Prior.ALIGN,
        )
        for i in range(9)
    ]
    result = hif.derive_zero_injection_prior("r1", probes)
    assert result.prior == hif.Prior.AGAINST
    assert result.consensus_count == 5

    leaked = list(probes)
    leaked[0] = leaked[0].model_copy(update={"target_rule_withheld": False})
    with pytest.raises(ValueError, match="LEAKED_TARGET_RULE"):
        hif.derive_zero_injection_prior("r1", leaked)


def test_three_vote_majority_matches_paper_protocol():
    assessment = hif.majority_vote(
        [
            hif.JudgeVote(judge_id="j1", status=hif.VerdictStatus.PASS),
            hif.JudgeVote(judge_id="j2", status=hif.VerdictStatus.FAIL),
            hif.JudgeVote(judge_id="j3", status=hif.VerdictStatus.PASS),
        ]
    )
    assert assessment.status == hif.VerdictStatus.PASS
    with pytest.raises(ValueError, match="THREE_VOTES"):
        hif.majority_vote(
            [hif.JudgeVote(judge_id="j1", status=hif.VerdictStatus.PASS)]
        )


def test_acc_facc_apacc_and_dwacc_are_recomputed_from_binary_verdicts():
    library = {
        "r1": rule("r1", prior=hif.Prior.AGAINST),
        "r2": rule("r2", prior=hif.Prior.ALIGN),
        "r3": rule("r3", prior=hif.Prior.AGAINST),
    }
    rows = [
        verdict("a", "i1", 0, "r1", hif.VerdictStatus.PASS),
        verdict("b", "i1", 0, "r1", hif.VerdictStatus.FAIL),
        verdict("c", "i1", 0, "r1", hif.VerdictStatus.FAIL),
        verdict("a", "i1", 0, "r2", hif.VerdictStatus.PASS),
        verdict("b", "i1", 0, "r2", hif.VerdictStatus.PASS),
        verdict("c", "i1", 0, "r2", hif.VerdictStatus.PASS),
        verdict("a", "i2", 0, "r3", hif.VerdictStatus.PASS),
        verdict("b", "i2", 0, "r3", hif.VerdictStatus.FAIL),
        verdict("c", "i2", 0, "r3", hif.VerdictStatus.NO_OPPORTUNITY),
    ]
    metrics = hif.compute_metrics(rows, library)
    by_agent = {row.agent_id: row for row in metrics.agents}
    assert by_agent["a"].accuracy == 1.0
    assert by_agent["a"].filtered_accuracy == 1.0
    assert by_agent["a"].against_prior_accuracy == 1.0
    assert by_agent["b"].accuracy == pytest.approx(1 / 3)
    assert by_agent["b"].filtered_accuracy == 0.0
    assert by_agent["b"].against_prior_accuracy == 0.0
    assert by_agent["c"].accuracy == 0.5
    assert by_agent["c"].against_prior_accuracy == 0.0
    assert by_agent["a"].discrimination_weighted_accuracy is not None
    assert all(weight >= 0 for weight in metrics.discrimination_weights.values())


def test_filtered_accuracy_is_cohort_relative():
    library = {"r1": rule("r1")}
    same = [
        verdict("a", "i", 0, "r1", hif.VerdictStatus.PASS),
        verdict("b", "i", 0, "r1", hif.VerdictStatus.PASS),
    ]
    assert hif.compute_metrics(same, library).agents[0].filtered_accuracy is None
    changed = [*same, verdict("c", "i", 0, "r1", hif.VerdictStatus.FAIL)]
    assert hif.compute_metrics(changed, library).agents[0].filtered_accuracy == 1.0


def test_common_support_excludes_nonbinary_or_missing_agent_keys():
    rows = [
        verdict("a", "i1", 0, "r1", hif.VerdictStatus.PASS),
        verdict("b", "i1", 0, "r1", hif.VerdictStatus.FAIL),
        verdict("a", "i2", 0, "r1", hif.VerdictStatus.PASS),
        verdict("b", "i2", 0, "r1", hif.VerdictStatus.NO_OPPORTUNITY),
    ]
    support = hif.common_support(rows)
    assert len(support) == 2
    assert {row.item_id for row in support} == {"i1"}


def test_cascade_dedup_retains_highest_severity_failure():
    library = {
        "must": rule("must", severity=hif.Severity.MUST),
        "should": rule("should", severity=hif.Severity.SHOULD),
    }
    rows = [
        verdict(
            "a", "i", 0, "must", hif.VerdictStatus.FAIL, cascade_id="artifact-x"
        ),
        verdict(
            "a", "i", 0, "should", hif.VerdictStatus.FAIL, cascade_id="artifact-x"
        ),
    ]
    deduped = hif.deduplicate_cascades(rows, library)
    assert deduped[0].status == hif.VerdictStatus.FAIL
    assert deduped[1].status == hif.VerdictStatus.NO_OPPORTUNITY


def test_cascade_fairness_excludes_design_gap_at_half_of_five_agents():
    rows = [
        verdict(
            f"a{i}",
            "i",
            0,
            "r1",
            (
                hif.VerdictStatus.NO_OPPORTUNITY
                if i < 3
                else hif.VerdictStatus.PASS
            ),
            missing_artifact_ref="artifact-x" if i < 3 else None,
        )
        for i in range(5)
    ]
    assert hif.cascade_fairness_exclusions(rows) == frozenset({"r1"})


def test_failure_decomposition_comes_from_modality_not_reason_text():
    library = {
        "req": rule("req", modality=hif.Modality.REQUIRE),
        "forbid": rule("forbid", modality=hif.Modality.FORBID),
        "prefer": rule("prefer", modality=hif.Modality.PREFER),
    }
    rows = [
        verdict("a", "i", 0, "req", hif.VerdictStatus.FAIL, reason="irrelevant"),
        verdict("a", "i", 0, "forbid", hif.VerdictStatus.FAIL, reason="same"),
        verdict("a", "i", 0, "prefer", hif.VerdictStatus.PASS, reason="same"),
    ]
    by_class = {
        row.failure_class: row for row in hif.decompose_failures(rows, library)
    }
    assert by_class[hif.FailureClass.SHORTFALL].failures == 1
    assert by_class[hif.FailureClass.OVERSTEP].failures == 1
    assert by_class[hif.FailureClass.PREFERENCE].failures == 0


def test_grouped_accuracy_preserves_surface_and_family_axes():
    library = {"r1": rule("r1")}
    rows = [
        verdict("a", "i", 0, "r1", hif.VerdictStatus.PASS),
        verdict("b", "i", 0, "r1", hif.VerdictStatus.FAIL),
    ]
    assert hif.grouped_accuracy(rows, library, by="surface") == {"PF": 0.5}
    assert hif.grouped_accuracy(rows, library, by="family") == {"workflow": 0.5}


def test_panel_item_cardinality_and_surface_fit_are_admitted_explicitly():
    library = {f"r{i}": rule(f"r{i}") for i in range(25)}
    scenario = hif.Scenario(
        scenario_id="s",
        domain="backend",
        task="fix",
        fixture_ref="fixture",
    )
    item = hif.BenchmarkItem(
        item_id="i",
        scenario=scenario,
        user_turns=("fix it",),
        placements=tuple(
            hif.place_constraint(
                library[f"r{i}"], hif.Surface.PROJECT_FILE
            )
            for i in range(25)
        ),
    )
    admission = hif.admit_panel_item(item, library)
    assert admission.accepted
    assert admission.rule_count == 25
    assert admission.scorable_count == 25


def test_snapshot_replay_is_deterministic_and_excludes_no_opportunity():
    constraint = rule("r1")
    snapshot = hif.EvaluationSnapshot(
        library=(constraint,),
        verdicts=(
            verdict("a", "i", 0, "r1", hif.VerdictStatus.PASS),
            verdict("a", "i", 1, "r1", hif.VerdictStatus.NO_OPPORTUNITY),
        ),
    )
    first = hif.replay(snapshot)
    second = hif.replay(snapshot)
    assert first == second
    assert first.metrics.agents[0].accuracy == 1.0
    assert first.snapshot_fingerprint == snapshot.snapshot_fingerprint


def test_bradley_terry_recovers_surface_precedence_from_conflicts():
    surfaces = [
        hif.Surface.SYSTEM_PROMPT,
        hif.Surface.PROJECT_FILE,
        hif.Surface.USER_INSTRUCTION,
        hif.Surface.TOOL_DESCRIPTION,
        hif.Surface.SKILL_DESCRIPTION,
    ]
    strength = {
        hif.Surface.SYSTEM_PROMPT: 5,
        hif.Surface.PROJECT_FILE: 5,
        hif.Surface.USER_INSTRUCTION: 5,
        hif.Surface.TOOL_DESCRIPTION: 3,
        hif.Surface.SKILL_DESCRIPTION: 1,
    }
    rows = []
    for model in ("m1", "m2"):
        for pair_no, left in enumerate(surfaces):
            for right in surfaces[pair_no + 1 :]:
                winner = (
                    left
                    if strength[left] >= strength[right]
                    else right
                )
                rows.append(
                    hif.ConflictRun(
                        model_id=model,
                        pair_id=f"{left.value}-{right.value}",
                        direction="AB",
                        surface_a=left,
                        surface_b=right,
                        winner=winner,
                    )
                )
    fit = hif.bradley_terry(rows)
    assert fit.decisive_runs == len(rows)
    assert (
        fit.log_strengths[hif.Surface.TOOL_DESCRIPTION]
        > fit.log_strengths[hif.Surface.SKILL_DESCRIPTION]
    )
    assert min(
        fit.log_strengths[surface]
        for surface in (
            hif.Surface.SYSTEM_PROMPT,
            hif.Surface.PROJECT_FILE,
            hif.Surface.USER_INSTRUCTION,
        )
    ) > fit.log_strengths[hif.Surface.TOOL_DESCRIPTION]
