from gymact.research_runtime.identity import RunIdentity

def test_identity_contract():
    assert RunIdentity("s").subject == "s"
