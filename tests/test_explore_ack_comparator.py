from gymact.explore_ack_comparator import evaluate
from gymact.explore_ack_protocols import Protocol, ProtocolKind
from gymact.explore_ack_witness import WitnessKind

def test_all_and_quorum_remain_semantically_distinct():
    keys = frozenset({"a", "b", "c"})
    frontier = {"a": WitnessKind.DISCHARGED, "b": WitnessKind.DISCHARGED}
    all_result = evaluate(Protocol(ProtocolKind.ALL), frontier, keys)
    quorum = evaluate(Protocol(ProtocolKind.QUORUM, quorum=2), frontier, keys)
    assert not all_result.complete and quorum.complete
