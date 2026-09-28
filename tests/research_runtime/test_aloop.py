from gymact.research_runtime.aloop import AutonomicLoop

def test_aloop_contract():
    assert AutonomicLoop().state == "observe"
