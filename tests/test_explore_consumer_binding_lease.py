from datetime import datetime,timedelta,timezone
from gymact.explore_consumer_binding.lease import EvidenceLease
def test_lease_half_open():
    t=datetime.now(timezone.utc); l=EvidenceLease(t,t+timedelta(seconds=1)); assert l.contains(t); assert not l.contains(t+timedelta(seconds=1))
