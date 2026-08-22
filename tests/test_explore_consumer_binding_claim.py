import pytest
from gymact.explore_consumer_binding.claim import ConsumptionClaim
from gymact.explore_consumer_binding.subject import Subject
def test_component_required():
    s=Subject('o/r','a'*40)
    with pytest.raises(ValueError,match='REFUSED_EMPTY_COMPONENT'): ConsumptionClaim(s,s,'','b'*64,'FOCUSED')
