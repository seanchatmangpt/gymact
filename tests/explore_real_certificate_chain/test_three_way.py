from fractions import Fraction

import pytest

from gymact.explore_real_certificate_chain.dual import bind_dual
from gymact.explore_real_certificate_chain.oracle import bind_oracle
from gymact.explore_real_certificate_chain.primal import bind_primal
from gymact.explore_real_certificate_chain.pipeline import certify


def test_three_way_certificate_chain_accepts_exact_agreement() -> None:
    subject = "seanchatmangpt/gymact@" + "a" * 40 + "#transport"
    chain = certify(
        bind_primal(subject, Fraction(3, 2), "plan"),
        bind_dual(subject, Fraction(3, 2), "dual"),
        bind_oracle(subject, Fraction(3, 2), "oracle"),
    )
    assert chain.value == Fraction(3, 2)


def test_three_way_certificate_chain_refuses_oracle_divergence() -> None:
    subject = "seanchatmangpt/gymact@" + "a" * 40 + "#transport"
    with pytest.raises(ValueError, match="ORACLE_DIVERGENCE"):
        certify(
            bind_primal(subject, Fraction(1), "plan"),
            bind_dual(subject, Fraction(1), "dual"),
            bind_oracle(subject, Fraction(2), "oracle"),
        )
