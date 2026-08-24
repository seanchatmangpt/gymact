from fractions import Fraction
import pytest

from gymact.explore_certificate_federation.authority import ActionClass, require_authority
from gymact.explore_certificate_federation.independence import ValidatorIdentity, require_independent
from gymact.explore_certificate_federation.quorum import require_effective_quorum
from gymact.explore_certificate_federation.refusal import FederationRefusal


def test_independence_quorum_and_authority_fences() -> None:
    validators = (
        ValidatorIdentity("impl-a", "model-a", "root-a"),
        ValidatorIdentity("impl-b", "model-b", "root-b"),
    )
    require_independent(validators)
    assert require_effective_quorum(2, Fraction(1, 4), Fraction(3, 2)) >= Fraction(3, 2)
    with pytest.raises(FederationRefusal, match="PSEUDO_INDEPENDENCE"):
        require_independent((validators[0], validators[0]))
    with pytest.raises(FederationRefusal, match="UNRECEIPTED_ACTUATION"):
        require_authority(ActionClass.DO)
    require_authority(ActionClass.DO, "BRCE")
