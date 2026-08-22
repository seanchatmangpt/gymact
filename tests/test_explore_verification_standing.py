from gymact.explore_verification.standing import standing


def test_success_ceiling_and_failure_dominance():
    assert standing(["PASS"]) == "PARTIAL_ALIVE"
    assert standing(["PASS", "FAIL"]) == "BUILD_BROKEN"
