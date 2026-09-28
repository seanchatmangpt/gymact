from gymact.research_runtime.budget import AttemptBudget

def test_budget_contract():
    assert AttemptBudget(2).limit == 2
