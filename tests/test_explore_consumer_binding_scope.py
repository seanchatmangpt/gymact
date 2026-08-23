from gymact.explore_consumer_binding.scope import scope_satisfies
def test_scope_anti_laundering():
    assert not scope_satisfies('FOCUSED','REPOSITORY')
    assert scope_satisfies('REPOSITORY','FOCUSED')
