from gymact.explore_verification.selection import pareto


def test_pareto_removes_only_dominated_strategy():
    assert pareto(
        {
            "a": {"coverage": 1, "reversible": 1},
            "b": {"coverage": 2, "reversible": 1},
        }
    ) == ("b",)
