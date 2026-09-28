from gymact.runtime_evolution.racap_runtime import PairedWorld


def test_promotion_requires_positive_delta():
    assert PairedWorld("S", 1, 2).promotes()
