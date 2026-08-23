import pytest
from gymact.explore_composition_selector_calibration import ActionClass,Receipt,Refused,admit,replay

def test_authority_and_replay_fence():
    with pytest.raises(Refused): admit(ActionClass.DO)
    r=Receipt('s','MAX_COVERAGE','CONSERVATIVE','PARTIAL_ALIVE',False)
    assert replay(r,r.digest())=='REPLAY_MATCH'
    with pytest.raises(Refused): replay(r,'0'*64)
