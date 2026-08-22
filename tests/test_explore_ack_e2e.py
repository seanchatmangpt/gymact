import pytest
from gymact.explore_ack_authority import Authority, Phase, admit_phase
from gymact.explore_ack_engine import qualify
from gymact.explore_ack_identity import Subject
from gymact.explore_ack_invalidation import Invalidation, InvalidationReason
from gymact.explore_ack_witness import Witness, WitnessKind

def test_e2e_compares_protocols_and_fences_do():
    producer = Subject("o/p", "a" * 40, "producer")
    a = Subject("o/a", "b" * 40, "consumer")
    b = Subject("o/b", "c" * 40, "consumer")
    c = Subject("o/c", "d" * 40, "consumer")
    event = Invalidation("evt", producer, 2, InvalidationReason.BUILD_BROKEN)
    witnesses = []
    for consumer in (a, b):
        witnesses.extend((Witness("evt", consumer, WitnessKind.DELIVERED, 1), Witness("evt", consumer, WitnessKind.ACKNOWLEDGED, 2), Witness("evt", consumer, WitnessKind.DISCHARGED, 3, "receipt")))
    authority = Authority("explore", frozenset({Phase.SELECT, Phase.CONSTRUCT}))
    result = qualify(event, (a, b, c), tuple(witnesses), frozenset({a.key}), authority)
    by_protocol = {r.protocol: r for r in result.alternatives}
    assert not by_protocol["ALL"].complete
    assert by_protocol["QUORUM"].complete and by_protocol["CRITICAL_PATH"].complete
    assert result.receipt.standing == "ALIVE"
    with pytest.raises(PermissionError, match="REFUSED_UNRECEIPTED_ACTUATION"):
        admit_phase(authority, Phase.DO)
