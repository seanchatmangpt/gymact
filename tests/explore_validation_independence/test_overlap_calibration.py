from fractions import Fraction

from gymact.explore_validation_independence import (
    Calibration,
    Evidence,
    EvidenceGraph,
    Interval,
    Provenance,
    Subject,
    ValidationCase,
    ancestry_overlap,
)


def test_shared_ancestry_is_measured_and_calibration_is_empirical():
    subject = Subject.parse("seanchatmangpt/gymact@" + "a" * 40 + "#" + "b" * 64)
    provenance = Provenance("i", "m", "d")
    root = Evidence("root", subject, 1, Interval(Fraction(1, 2), Fraction(1)), provenance)
    left = Evidence(
        "left",
        subject,
        1,
        Interval(Fraction(1, 2), Fraction(1)),
        provenance,
        ("root",),
    )
    right = Evidence(
        "right",
        subject,
        1,
        Interval(Fraction(1, 2), Fraction(1)),
        provenance,
        ("root",),
    )
    overlap = ancestry_overlap(EvidenceGraph((root, left, right)), "left", "right")
    assert overlap.ratio == Fraction(1, 3)
    cases = (
        ValidationCase("1", Fraction(0), Fraction(1), Fraction(1, 2)),
        ValidationCase("2", Fraction(1, 4), Fraction(3, 4), Fraction(1, 2)),
    )
    calibration = Calibration.from_cases(2, "digest", cases)
    assert calibration.coverage == 1
