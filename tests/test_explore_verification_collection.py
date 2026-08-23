from gymact.explore_verification.collection import collection_boundary


def test_collection_error_is_build_broken():
    assert collection_boundary(897, 1, 10) == "BUILD_BROKEN"
    assert collection_boundary(897, 0, 10) == "PARTIAL_ALIVE"
