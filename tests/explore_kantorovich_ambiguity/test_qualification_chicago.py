from fractions import Fraction
from gymact.explore_kantorovich_ambiguity import qualify, replay

def test_bounded_independent_oracle_candidate_caps_at_partial_alive():
    q=qualify(
        subject="seanchatmangpt/gymact@"+"f"*40+"#kantorovich",
        worst_loss=Fraction(2),max_loss=Fraction(3),
        oracle_gap=Fraction(),max_oracle_gap=Fraction(),
        dependencies=("ALIVE","PARTIAL_ALIVE"),
    )
    assert q.standing=="PARTIAL_ALIVE"
    assert q.receipt is not None and replay(q.receipt)

def test_broken_dependency_is_failure_dominant_and_suppresses_receipt():
    q=qualify(
        subject="x",worst_loss=Fraction(),max_loss=Fraction(1),
        oracle_gap=Fraction(),max_oracle_gap=Fraction(),
        dependencies=("ALIVE","BUILD_BROKEN"),
    )
    assert q.standing=="BUILD_BROKEN"
    assert q.receipt is None
