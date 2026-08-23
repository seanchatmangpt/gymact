import pytest

from gymact.explore_ack_admission import admit
from gymact.explore_ack_identity import Subject
from gymact.explore_ack_invalidation import Invalidation, InvalidationReason
from gymact.explore_ack_witness import Witness, WitnessKind


def test_causal_gap_is_refused():
    producer = Subject("o/p", "a" * 40, "producer")
    consumer = Subject("o/c", "b" * 40, "consumer")
    event = Invalidation("evt", producer, 1, InvalidationReason.BUILD_BROKEN)
    with pytest.raises(ValueError, match="REFUSED_CAUSAL_GAP"):
        admit(
            event,
            (consumer,),
            (Witness("evt", consumer, WitnessKind.ACKNOWLEDGED, 1),),
        )
