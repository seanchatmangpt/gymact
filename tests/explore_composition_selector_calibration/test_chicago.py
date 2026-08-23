from gymact.explore_composition_selector_calibration import Standing,Subject,qualify,replay
from gymact.explore_composition_selector_calibration.methodology import REQUIRED

def test_chicago_selector_qualification_and_failure_suppression():
    subject=Subject.parse('seanchatmangpt/gymact@'+'a'*40+'#'+'b'*64)
    q=qualify(subject,'MAX_COVERAGE','CONSERVATIVE',REQUIRED,(Standing.PARTIAL_ALIVE,Standing.PARTIAL_ALIVE))
    assert q.standing is Standing.PARTIAL_ALIVE and q.receipt is not None
    assert replay(q.receipt,q.receipt.digest())=='REPLAY_MATCH'
    broken=qualify(subject,'MIN_WIDTH','INDEPENDENT',REQUIRED,(Standing.PARTIAL_ALIVE,Standing.BUILD_BROKEN))
    assert broken.standing is Standing.BUILD_BROKEN and broken.receipt is None
