import pytest

from gymact.explore_ack_identity import Subject
from gymact.explore_ack_invalidation import Invalidation, InvalidationReason


def test_invalidation_requires_producer_and_positive_epoch():
    consumer = Subject("o/r", "b" * 40, "consumer")
    with pytest.raises(ValueError, match="REFUSED_INVALID_INVALIDATION"):
        Invalidation("e", consumer, 1, InvalidationReason.BUILD_BROKEN)
