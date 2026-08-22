from gymact.explore_supersession.differential import differential


def test_differential_reports_exact_changed_paths():
    left = {"frontier": {"standing": "PARTIAL_ALIVE", "runs": ["old"]}}
    right = {"frontier": {"standing": "BUILD_BROKEN", "runs": ["new"]}}
    assert differential(left, right) == (
        "$.frontier.runs[0]",
        "$.frontier.standing",
    )
