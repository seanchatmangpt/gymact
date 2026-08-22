from gymact.explore_verification.candidates import Candidate, discover


def test_candidate_discovery_preserves_reversible_alternatives():
    items = [
        Candidate("a", frozenset({"x"})),
        Candidate("b", frozenset({"x", "y"})),
        Candidate("c", frozenset({"x"}), False),
    ]
    assert [item.name for item in discover(items, {"x"})] == ["a", "b"]
