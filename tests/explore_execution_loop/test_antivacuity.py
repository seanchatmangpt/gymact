"""Anti-vacuity court: a recovery test that passes without the fault carries
no bits.

For every corpus scenario the MUTATED variant (same builder, fault NOT
injected via ``inject=False``) is executed, and the scenario's required
fault-marker OCEL events are asserted ABSENT-or-insufficient: the marker
assertion that passes under the fault must FAIL without it. A mutant that
still satisfies the fault markers means the court is vacuous and this test
fails.

Guard scenarios (F29/F30) are excluded: their fault is an illegal
construction whose 'mutant' is the legal construction, covered in
test_illegal_outcomes.py.
"""

from __future__ import annotations


def test_fault_markers_vanish_without_the_fault(manifest, scenario, seed, court):
    builder = court.BUILDERS[scenario["id"]]
    mutant = builder(seed, inject=False)
    results = mutant.run()
    observed = court.event_types(results)
    markers = set(scenario["required_ocel_events"])
    surviving = markers & observed
    assert not surviving, (
        f"VACUOUS COURT {scenario['id']}: fault markers {sorted(surviving)} still "
        f"present with the fault NOT injected (observed={sorted(observed)})"
    )


def test_mutant_worlds_are_healthy_or_legally_terminal(manifest, scenario, seed, court):
    """The no-fault world must be a HEALTHY world: terminal Recover/ALIVE --
    unless the scenario's fault-free semantics are a legal typed terminal
    (e.g. F09's deadline is the fault). This pins the mutant's meaning: it is
    the world the fault is defined against."""
    builder = court.BUILDERS[scenario["id"]]
    mutant = builder(seed, inject=False)
    results = mutant.run()
    terminal = results[-1]
    healthy = terminal.outcome == "Recover" and terminal.standing.value == "ALIVE"
    if not healthy:
        # allowed only when the scenario's fault injection is intrinsic to the
        # request/constraint itself (deadline, capability demand), in which
        # case the mutant still must be a LEGAL terminal, never a crash.
        assert terminal.outcome in {"Recover", "TypedBlock"}, (
            f"{scenario['id']} mutant is not a legal terminal: {terminal.outcome} "
            f"reason={terminal.typed_reason}"
        )


def test_exactly_once_invariant_holds_under_crash_after_actuation(court):
    """F02's exactly-once post-condition must be FALSE for the naive mutant
    where the journal is lost: the loop cannot prove the actuation happened,
    so actuation_count would be 0 with a TypedBlock -- demonstrating the
    post-condition is load-bearing, not decorative."""
    crashed_with_journal = court.BUILDERS["L7-F02-worker-sigkill-after-actuation-journal-present"](
        7, True
    ).run()[0]
    assert crashed_with_journal.actuation_count == 1
    journal_lost = court.BUILDERS["L7-F03-worker-sigkill-after-actuation-journal-lost"](
        7, True
    ).run()[0]
    assert journal_lost.outcome == "TypedBlock"
    assert journal_lost.broken_term is not None
    assert journal_lost.broken_term.value == "R_missing_consequence"
    assert journal_lost.actuation_count == 0
