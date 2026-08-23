import pytest

from gymact.explore_decision_realization import Candidate, Decision, DeferRealization, LabeledDecision, ObservedAlternative, Refused, Strategy, directional_rates, frontier, observed_regret, select


def test_realized_regret_defer_and_selector_plurality() -> None:
    chosen = ObservedAlternative("chosen", 0.6)
    assert observed_regret(chosen, (ObservedAlternative("alt", 0.2),)) == pytest.approx(0.4)
    with pytest.raises(Refused, match="UNOBSERVED_COUNTERFACTUAL"):
        observed_regret(chosen, (ObservedAlternative("hidden", 0.1, False),))
    assert DeferRealization(0.6, 0.3, 0.2, 0.1).net_value == pytest.approx(0.4)
    rates = directional_rates((LabeledDecision(Decision.INDEPENDENT, False), LabeledDecision(Decision.DEPENDENT, True), LabeledDecision(Decision.DEFER, True), LabeledDecision(Decision.INDEPENDENT, True)))
    assert rates.false_independent == pytest.approx(0.25)
    candidates = (
        Candidate("risk", Decision.DEPENDENT, 0.1, 0.2, 0.1, 0.2),
        Candidate("safe", Decision.DEPENDENT, 0.2, 0.0, 0.0, 0.1),
        Candidate("info", Decision.INDEPENDENT, 0.3, 0.1, 0.9, 0.3),
        Candidate("defer", Decision.DEFER, 0.25, 0.05, 0.5, 0.01),
    )
    assert [select(candidates, strategy).name for strategy in Strategy] == ["risk", "safe", "info", "defer"]
    assert {item.name for item in frontier(candidates)} == {"risk", "safe", "info", "defer"}
