from gymact.research_runtime.replay import ReplayKey

def test_replay_contract():
    assert ReplayKey("s","p","o").subject == "s"
