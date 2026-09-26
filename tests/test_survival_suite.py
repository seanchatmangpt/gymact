from __future__ import annotations

import pytest

from gymact.survival_faults import SurvivalFaultKind
from gymact.survival_suite import (
    canonical_fault_kinds,
    canonical_fault_suite,
    canonical_policy_suite,
    canonical_trace_template,
)


def test_canonical_policy_suite_spans_machinery_ladder_once() -> None:
    policies = canonical_policy_suite()

    assert len(policies) == 5
    assert len({policy.policy_id for policy in policies}) == 5
    assert len({policy.machinery for policy in policies}) == 5
    assert all(policy.grants_do_authority is False for policy in policies)


def test_canonical_factor_suite_is_full_nonempty_reversible_grid() -> None:
    factors = canonical_fault_suite()

    assert [factor.name for factor in factors] == [
        "authority",
        "transport",
        "evidence",
        "terminal_signal",
    ]
    assert all(len(factor.levels) == 3 for factor in factors)


def test_canonical_fault_kinds_cover_enum_without_duplicates() -> None:
    kinds = canonical_fault_kinds()

    assert set(kinds) == set(SurvivalFaultKind)
    assert len(kinds) == len(set(kinds))


def test_canonical_trace_template_is_bounded_replayable_skeleton() -> None:
    template = canonical_trace_template(10)

    assert [step.step for step in template.steps] == [1, 9, 10]
    assert [step.phase for step in template.steps] == ["OBSERVE", "VERIFY", "DO"]
    assert template.steps[-1].receipt_id == "synthetic:baseline-receipt"
    assert template.steps[-1].replay_verified is True


@pytest.mark.parametrize("horizon", [0, 1, 2, True])
def test_canonical_trace_template_refuses_too_short_horizon(horizon) -> None:
    with pytest.raises(ValueError, match="HORIZON_MIN_3"):
        canonical_trace_template(horizon)
