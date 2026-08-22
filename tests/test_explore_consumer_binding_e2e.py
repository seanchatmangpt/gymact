import pytest
from datetime import datetime,timedelta,timezone
from gymact.explore_consumer_binding.claim import ConsumptionClaim
from gymact.explore_consumer_binding.engine import qualify,require_do
from gymact.explore_consumer_binding.evidence import Evidence
from gymact.explore_consumer_binding.lease import EvidenceLease
from gymact.explore_consumer_binding.subject import Subject
def test_current_binding_qualifies_without_do():
    s=Subject('o/r','a'*40); now=datetime.now(timezone.utc); e=Evidence(s,'b'*64,'v1','REPOSITORY','PASS'); c=ConsumptionClaim(s,s,'x','b'*64,'FOCUSED')
    out=qualify(c,e,EvidenceLease(now-timedelta(seconds=1),now+timedelta(seconds=1)),now,'b'*64,'v1')
    assert out['standing']=='PARTIAL_ALIVE'; assert not out['actuation_performed']
    with pytest.raises(PermissionError,match='REFUSED_UNRECEIPTED_ACTUATION'): require_do(False)
