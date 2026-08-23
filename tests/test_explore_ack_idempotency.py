from gymact.explore_ack_admission import admit
from gymact.explore_ack_identity import Subject
from gymact.explore_ack_invalidation import Invalidation, InvalidationReason
from gymact.explore_ack_witness import Witness, WitnessKind


def test_duplicate_delivery_is_idempotent():
    producer = Subject("o/p", "a" * 40, "producer")
    consumer = Subject("o/c", "b" * 40, "consumer")
    event = Invalidation("evt", producer, 1, InvalidationReason.BUILD_BROKEN)
    witness = Witness("evt", consumer, WitnessKind.DELIVERED, 1)
    output = admit(event, (consumer,), (witness, witness))
    assert output.duplicates == 1
    assert output.frontier[consumer.key] is WitnessKind.DELIVERED
