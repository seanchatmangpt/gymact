from gymact.explore_ack_admission import admit
from gymact.explore_ack_identity import Subject
from gymact.explore_ack_invalidation import Invalidation, InvalidationReason
from gymact.explore_ack_witness import Witness, WitnessKind

def test_duplicate_delivery_is_idempotent():
    p = Subject("o/p", "a" * 40, "producer")
    c = Subject("o/c", "b" * 40, "consumer")
    event = Invalidation("evt", p, 1, InvalidationReason.BUILD_BROKEN)
    witness = Witness("evt", c, WitnessKind.DELIVERED, 1)
    out = admit(event, (c,), (witness, witness))
    assert out.duplicates == 1 and out.frontier[c.key] is WitnessKind.DELIVERED
