from gymact.explore_consumer_binding.drift import classify_drift
from gymact.explore_consumer_binding.evidence import Evidence
from gymact.explore_consumer_binding.subject import Subject
def test_drift_is_typed():
    e=Evidence(Subject('o/r','a'*40),'b'*64,'v1','FOCUSED','PASS')
    assert classify_drift(e,'c'*64,'v1')=='SUPERSEDED_RECEIPT'
