import pytest
from gymact.explore_kantorovich_ambiguity.authority import Action, admit
from gymact.explore_kantorovich_ambiguity.receipt import Receipt, issue, replay
from gymact.explore_kantorovich_ambiguity import Refused

def test_do_requires_brce_and_receipt_is_no_actuation():
    with pytest.raises(Refused, match="DO_REQUIRES_BRCE"):
        admit(Action.DO)
    admit(Action.DO,"BRCE")
    receipt=issue({"subject":"x","authority":"VERIFY","actuation_performed":False})
    assert replay(receipt)

def test_tamper_refuses_replay():
    receipt=issue({"subject":"x","authority":"VERIFY","actuation_performed":False})
    bad=Receipt({**receipt.body,"subject":"y"},receipt.digest)
    with pytest.raises(Refused, match="RECEIPT_DIGEST_MISMATCH"):
        replay(bad)
