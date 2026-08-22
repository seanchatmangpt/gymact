from gymact.explore_consumer_binding.claim import ConsumptionClaim
from gymact.explore_consumer_binding.receipt import manufacture,replay
from gymact.explore_consumer_binding.subject import Subject
def test_receipt_replay_deterministic():
    s=Subject('o/r','a'*40); c=ConsumptionClaim(s,s,'x','b'*64,'FOCUSED'); r=manufacture(c,'PARTIAL_ALIVE')
    assert replay(c,'PARTIAL_ALIVE',r); assert not replay(c,'BUILD_BROKEN',r)
