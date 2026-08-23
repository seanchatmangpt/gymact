from gymact.explore_consumer_binding.dependency import propagate
def test_broken_producer_blocks_consumer():
    assert propagate({'p':'BUILD_BROKEN','c':'PARTIAL_ALIVE'},{'c':{'p'}})['c']=='BLOCKED'
