import pytest

from gymact.explore_kantorovich_duality.authority import ActionClass, admit


def test_direct_do_refuses() -> None:
    with pytest.raises(ValueError, match="UNRECEIPTED_ACTUATION"):
        admit(ActionClass.DO)


def test_brce_broker_admits_do_boundary() -> None:
    admit(ActionClass.DO, broker="BRCE")
