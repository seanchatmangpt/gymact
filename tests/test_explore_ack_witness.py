import pytest

from gymact.explore_ack_identity import Subject
from gymact.explore_ack_witness import Witness, WitnessKind


def test_discharge_requires_receipt_digest():
    consumer = Subject("o/r", "c" * 40, "consumer")
    with pytest.raises(ValueError, match="REFUSED_DISCHARGE_WITHOUT_RECEIPT"):
        Witness("e", consumer, WitnessKind.DISCHARGED, 3)
