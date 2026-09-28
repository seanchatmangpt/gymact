from gymact.research_runtime.policy import RuntimePolicy

def test_policy_contract():
    assert RuntimePolicy(("a","b")).max_attempts == 3
