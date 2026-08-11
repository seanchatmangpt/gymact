"""Chicago-style tests for `gymact.epistemic_process_kernel.next_kernel_action`
-- the pure, deterministic decision a real live cluster run exposed a real
bug in (4 SUPPORTED + 0 UNKNOWN was wrongly treated as closure, so
Discriminate never ran at all). No mocks, no LLM, no live cluster: this
function takes plain ints and returns a plain string, so the exact
regression is directly testable.
"""

from __future__ import annotations

from gymact.epistemic_process_kernel import next_kernel_action


def test_one_supported_zero_unknown_reaches_closure():
    """1 SUPPORTED + rest REFUTED (0 UNKNOWN) -- the discriminator must
    NOT run; this is a genuinely clean result."""
    assert next_kernel_action(supported_count=1, unknown_count=0) == "closure"


def test_multiple_supported_zero_unknown_discriminates():
    """The exact real shape a live cluster run produced: 4 SUPPORTED + 0
    UNKNOWN. This is over-determined, not resolved -- the discriminator
    MUST run to try to partition the survivors."""
    assert next_kernel_action(supported_count=4, unknown_count=0) == "discriminate"


def test_unknown_hypotheses_discriminate():
    """Any real UNKNOWN remaining (under-determined, with or without a
    concurrent SUPPORTED) means the discriminator MUST run."""
    assert next_kernel_action(supported_count=0, unknown_count=2) == "discriminate"
    assert next_kernel_action(supported_count=1, unknown_count=1) == "discriminate"


def test_all_refuted_does_not_fake_diagnosis():
    """0 SUPPORTED + 0 UNKNOWN (every real candidate was falsified) must
    never be silently treated as closure -- the kernel re-hypothesizes
    instead of calling Discriminate against an empty frontier or
    fabricating a forced diagnosis."""
    assert next_kernel_action(supported_count=0, unknown_count=0) == "rehypothesize"
