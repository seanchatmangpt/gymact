from datetime import UTC, datetime, timedelta

from gymact.explore_consumer_binding.lease import EvidenceLease


def test_lease_half_open():
    t = datetime.now(UTC)
    lease = EvidenceLease(t, t + timedelta(seconds=1))
    assert lease.contains(t)
    assert not lease.contains(t + timedelta(seconds=1))
