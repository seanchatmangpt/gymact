from datetime import datetime, timezone

import pytest

from gymact.explore_supersession.epoch import Epoch
from gymact.explore_supersession.subject import Refusal


def test_epoch_requires_timezone_and_forward_sequence():
    with pytest.raises(Refusal, match="REFUSED_NAIVE_EPOCH"):
        Epoch(datetime(2026, 8, 22))
    assert Epoch(datetime(2026, 8, 22, tzinfo=timezone.utc), 1).canonical()[1] == 1
