import pytest

from gymact.explore_supersession.candidates import Candidate, default_candidates
from gymact.explore_supersession.subject import Refusal


def test_candidate_graph_preserves_multiple_lawful_options():
    candidates = default_candidates()
    assert {c.storage for c in candidates} == {"memory", "jsonl"}
    assert {c.semantic for c in candidates} == {"exact-frontier", "supersession-graph"}
    with pytest.raises(Refusal, match="REFUSED_IRREVERSIBLE_EXPLORE_CANDIDATE"):
        Candidate("unsafe", "x", "x", "x", frozenset(), reversible=False)
