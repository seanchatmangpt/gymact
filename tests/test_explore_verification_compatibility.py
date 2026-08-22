from gymact.explore_verification.compatibility import compare


def test_shared_axis_compatibility_and_divergence():
    assert compare({"focused": "PASS"}, {"focused": "PASS", "repository": "FAIL"}) == "COMPATIBLE"
    assert compare({"repository": "PASS"}, {"repository": "FAIL"}) == "DIVERGED"
