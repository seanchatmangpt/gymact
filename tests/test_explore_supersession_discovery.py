from gymact.explore_supersession.candidates import default_candidates
from gymact.explore_supersession.discovery import discover


def test_discovery_preserves_all_capable_reversible_candidates():
    durable = discover(default_candidates(), frozenset({"durable"}))
    replay = discover(default_candidates(), frozenset({"replay"}))
    assert [candidate.name for candidate in durable] == ["jsonl-local"]
    assert len(replay) == 3
