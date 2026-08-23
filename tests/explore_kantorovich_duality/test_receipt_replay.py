from dataclasses import replace
from fractions import Fraction

import pytest

from gymact.explore_kantorovich_duality import DualityRefusal, Subject, manufacture_receipt, replay


def test_receipt_replays_and_tamper_refuses() -> None:
    subject = Subject.admit("seanchatmangpt/gymact", "b" * 40, "duality")
    receipt = manufacture_receipt(subject, Fraction(1), Fraction(1))
    replay(receipt)
    with pytest.raises(DualityRefusal, match="RECEIPT_DRIFT"):
        replay(replace(receipt, dual=Fraction(0)))
