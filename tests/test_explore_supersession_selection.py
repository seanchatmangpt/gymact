from gymact.explore_supersession.candidates import default_candidates
from gymact.explore_supersession.selection import pareto, weighted_select


def test_selection_is_reversible_and_deterministic():
    candidates = default_candidates()
    scores = {
        "memory-local": (2, 1),
        "jsonl-local": (3, 2),
        "graph-local": (3, 3),
    }
    frontier = pareto(candidates, scores)
    assert [candidate.name for candidate in frontier] == ["graph-local"]
    selected = weighted_select(candidates, scores, (2, 1))
    assert selected.name == "graph-local"
