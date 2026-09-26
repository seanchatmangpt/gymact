"""lifegym long-horizon scenarios: HONEST classification.

The lifegym checkout is ABSENT from this machine (searched ~/lifegym,
~/dev/lifegym, mdfind; only vendor copies inside OTHER lanes' repos exist,
outside lane-7 write authority). Per the lane contract that is
BLOCKED(INFORMATION: lifegym absent): the lifegym-owned semantics
(long-horizon multi-stage episodes with silent state changes) are exercised
here as SIMULATED-IN-PROCESS fakes inside the gymact harness. Nothing in
this module is a lifegym-native real-world run; the corpus manifest records
the same blocker (scenario L7-F31, repo_home field).
"""

from __future__ import annotations


def test_manifest_records_lifegym_blocker_honestly(court):
    manifest = court.load_manifest()
    lifegym = manifest["repos"]["lifegym"]
    assert lifegym["status"].startswith("BLOCKED_INFORMATION")
    scenario = next(s for s in manifest["scenarios"] if s["id"].startswith("L7-F31"))
    assert "ABSENT" in scenario["repo_home"]
    assert scenario["execution_class"] == "simulated-in-process"


def test_long_horizon_silent_mutation_is_recovered_without_humans(court):
    built = court.BUILDERS["L7-F31-lifegym-long-horizon-silent-stage-mutation"](7, inject=True)
    results = built.run()
    terminal = results[-1]
    assert terminal.outcome == "Recover", terminal.typed_reason
    assert terminal.standing.value == "ALIVE"
    assert terminal.episode_standing.value == "AUTONOMOUS"
    # the silent stage mutation WAS noticed by machinery, not by a human
    court.assert_required_events(results, ["reconcile.replan", "receipt.emit"])
    replans = [e for r in results for e in r.events if e.event_type == "reconcile.replan"]
    assert replans, "silent stage mutation was never detected"
    built.post(results)


def test_lifegym_mutant_completes_without_replans(court):
    """Anti-vacuity for the long-horizon court: without the silent mutation
    the episode completes with ZERO replan events (the fault markers vanish),
    proving the court detects the mutation and not stage progress itself."""
    built = court.BUILDERS["L7-F31-lifegym-long-horizon-silent-stage-mutation"](7, inject=False)
    results = built.run()
    assert results[-1].outcome == "Recover"
    replans = [e for r in results for e in r.events if e.event_type == "reconcile.replan"]
    assert replans == [], "no-fault world produced replans: court is vacuous"
