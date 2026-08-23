import pytest

from gymact.explore_composition_selector_calibration import Refused, Standing
from gymact.explore_composition_selector_calibration.methodology import (
    REQUIRED,
    require_closure,
)
from gymact.explore_composition_selector_calibration.standing import combine


def test_methodology_and_failure_dominance():
    with pytest.raises(Refused):
        require_closure(frozenset({"discovery"}))
    require_closure(REQUIRED)
    assert (
        combine((Standing.PARTIAL_ALIVE, Standing.BUILD_BROKEN))
        is Standing.BUILD_BROKEN
    )
