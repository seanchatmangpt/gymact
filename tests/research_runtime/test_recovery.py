from gymact.research_runtime.recovery import RecoveryPlan

def test_recovery_contract():
    assert RecoveryPlan(("bad",),"good").next_edge == "good"
