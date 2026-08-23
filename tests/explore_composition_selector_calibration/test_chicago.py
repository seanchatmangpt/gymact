from gymact.explore_composition_selector_calibration import (
    Standing,
    Subject,
    qualify,
    replay,
)
from gymact.explore_composition_selector_calibration.methodology import REQUIRED


def test_chicago_selector_qualification_and_failure_suppression():
    subject = Subject.parse("seanchatmangpt/gymact@" + "a" * 40 + "#" + "b" * 64)
    qualification = qualify(
        subject,
        "MAX_COVERAGE",
        "CONSERVATIVE",
        REQUIRED,
        (Standing.PARTIAL_ALIVE, Standing.PARTIAL_ALIVE),
    )
    assert qualification.standing is Standing.PARTIAL_ALIVE
    assert qualification.receipt is not None
    assert replay(qualification.receipt, qualification.receipt.digest()) == "REPLAY_MATCH"
    broken = qualify(
        subject,
        "MIN_WIDTH",
        "INDEPENDENT",
        REQUIRED,
        (Standing.PARTIAL_ALIVE, Standing.BUILD_BROKEN),
    )
    assert broken.standing is Standing.BUILD_BROKEN
    assert broken.receipt is None
