import pytest
from datetime import datetime,timedelta,timezone
from gymact.explore_consumer_binding.admission import admit
from gymact.explore_consumer_binding.claim import ConsumptionClaim
from gymact.explore_consumer_binding.evidence import Evidence
from gymact.explore_consumer_binding.lease import EvidenceLease
from gymact.explore_consumer_binding.subject import Subject
def test_superseded_receipt_refuses():
    s=Subject('o/r','a'*40); now=datetime.now(timezone.utc); e=Evidence(s,'b'*64,'v1','REPOSITORY','PASS'); c=ConsumptionClaim(s,s,'x','b'*64,'FOCUSED')
    with pytest.raises(ValueError,match='REFUSED_SUPERSEDED_RECEIPT'): admit(c,e,EvidenceLease(now-timedelta(seconds=1),now+timedelta(seconds=1)),now,'c'*64,'v1')
