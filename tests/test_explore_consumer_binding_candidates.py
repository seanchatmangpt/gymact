from gymact.explore_consumer_binding.candidates import admissible,discover
def test_multiple_reversible_candidates_preserved():
    assert {c.name for c in admissible(discover())}=={'memory','jsonl','sqlite'}
