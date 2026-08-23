import pytest

from gymact.explore_kantorovich_duality import ActionClass, DualityRefusal, admit_action


def test_direct_do_refuses_without_brce() -> None:
    admit_action(ActionClass.VERIFY)
    with pytest.raises(DualityRefusal, match="UNRECEIPTED_ACTUATION"):
        admit_action(ActionClass.DO)
    admit_action(ActionClass.DO, broker="BRCE")
