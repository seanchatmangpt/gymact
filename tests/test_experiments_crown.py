import pytest

from gymact.experiments import (
    AntiAgentPoint,
    FaultInjector,
    FaultKind,
    FaultPlan,
    IntelligenceRun,
    SelfPlayCase,
    TransitionEconomics,
    anti_agent_benchmark,
    evaluate_compile_out,
    run_self_play,
)


def test_fault_injection_is_bounded_and_occurrence_specific() -> None:
    injector = FaultInjector(
        [FaultPlan(fault=FaultKind.LOST_ACK, occurrence=2, operation_ref="act")]
    )
    assert not injector.decide("act").inject
    second = injector.decide("act")
    assert second.inject
    assert second.fault is FaultKind.LOST_ACK
    assert not injector.decide("act").inject
    with pytest.raises(ValueError, match="UNBOUNDED"):
        FaultInjector(
            [FaultPlan(fault=FaultKind.TIMEOUT, operation_ref="act", bounded=False)]
        )


def test_self_play_counts_incorrect_safety_crowns() -> None:
    cases = (
        SelfPlayCase(case_id="valid", expected_disposition="ALIVE"),
        SelfPlayCase(
            case_id="deny",
            expected_disposition="REFUSED",
            safety_critical=True,
        ),
    )
    good = run_self_play(cases, lambda case: case.expected_disposition)
    assert good.crown_safe
    assert good.passed == 2

    bad = run_self_play(cases, lambda case: "ALIVE")
    assert bad.incorrect_safety_crowns == 1
    assert not bad.crown_safe


def economics(repetitions: int, cost: float, tokens: int) -> TransitionEconomics:
    return TransitionEconomics(
        repetitions=repetitions,
        verified_transitions=repetitions,
        wall_time_s=max(1, repetitions / 10),
        monetary_cost=cost,
        human_intervention_factor=1,
        model_tokens=tokens,
    )


def test_anti_agent_benchmark_finds_crossover_and_marginal_advantage() -> None:
    report = anti_agent_benchmark(
        [
            AntiAgentPoint(
                repetitions=1,
                frontier=economics(1, 1, 100),
                gymact=economics(1, 3, 100),
            ),
            AntiAgentPoint(
                repetitions=100,
                frontier=economics(100, 100, 10_000),
                gymact=economics(100, 10, 0),
            ),
        ]
    )
    assert report.crossover_repetitions == 100
    assert report.gymact_lower_marginal_cost


def test_compile_out_requires_zero_tokens_and_identical_authority_verifier() -> None:
    cold = IntelligenceRun(
        regime="COLD",
        model_tokens=100,
        monetary_cost=2,
        wall_time_s=2,
        authority_policy_ref="p",
        verifier_ref="v",
        verified=True,
        receipt_ref="r1",
    )
    hot = IntelligenceRun(
        regime="HOT",
        model_tokens=0,
        monetary_cost=0.1,
        wall_time_s=0.1,
        authority_policy_ref="p",
        verifier_ref="v",
        verified=True,
        receipt_ref="r2",
    )
    assert evaluate_compile_out(cold, hot).compiled_out
    assert not evaluate_compile_out(
        cold,
        hot.model_copy(update={"authority_policy_ref": "weaker"}),
    ).compiled_out
