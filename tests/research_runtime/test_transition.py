from gymact.research_runtime.transition import Transition

def test_transition_contract():
    assert Transition("idle","run").admitted is False
