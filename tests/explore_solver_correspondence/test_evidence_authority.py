from fractions import Fraction

import pytest

from gymact.explore_solver_correspondence.authority import admit_authority
from gymact.explore_solver_correspondence.effective_evidence import (
    require_effective_quorum,
)
from gymact.explore_solver_correspondence.refusal import Refused


def test_correlated_verifiers_cannot_fake_quorum():
    with pytest.raises(Refused, match="PSEUDO_QUORUM"):
        require_effective_quorum(3, Fraction(1), Fraction(2))


def test_do_requires_brce():
    with pytest.raises(Refused, match="DO_REQUIRES_BRCE"):
        admit_authority("DO")
    admit_authority("DO", "BRCE")
