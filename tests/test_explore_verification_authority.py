import pytest

from gymact.explore_verification.authority import require


def test_select_admits_and_do_refuses():
    assert require("SELECT") == "SELECT"
    with pytest.raises(PermissionError, match="REFUSED_UNRECEIPTED_ACTUATION"):
        require("DO")
