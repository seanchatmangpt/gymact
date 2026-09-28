from gymact.research_runtime.authority import AuthorityFence

def test_authority_contract():
    assert AuthorityFence().allowed is False
