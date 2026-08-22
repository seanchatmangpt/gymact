from gymact.explore_ack_protocols import ProtocolKind, candidates

def test_three_reversible_protocols_are_preserved():
    options = candidates(5, frozenset({"critical"}))
    assert [c.kind for c in options] == [ProtocolKind.ALL, ProtocolKind.QUORUM, ProtocolKind.CRITICAL_PATH]
    assert options[1].quorum == 3
