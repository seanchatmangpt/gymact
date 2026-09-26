"""Illegal-outcome and guard court.

1. ``WaitForHumanToNotice`` is structurally unreachable: no ``outcome=`` in
   the kernel source ever names an IllegalOutcome member, and every occurrence
   of the member lives inside the enum definition or the court-facing
   ``asserted_illegal_outcome`` property.
2. The standing law: ASSISTED -> AUTONOMOUS raises; other transitions do not
   (anti-vacuity for the guard itself).
3. Receipt ext keys must be namespaced.
4. Every corpus receipt emitted by the loop carries only namespaced ext keys
   and the episode's required receipt fields (contract conformance).
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from gymact.execution_loop import (
    EpisodeStanding,
    ExecutionReceipt,
    LoopBudgetExceeded,
    loop_log,
)
from gymact.ocel import validate_ocel_log

KERNEL = Path(__file__).parents[2] / "src" / "gymact" / "execution_loop.py"

REQUIRED_RECEIPT_FIELDS = (
    "work_order_id",
    "origin_authority",
    "provider",
    "provider_execution_id",
    "subject_before",
    "subject_after",
    "commands",
    "consequences",
    "evidence",
    "exit_status",
    "timestamps",
    "replay_binding",
)


def test_wait_for_human_to_notice_is_structurally_unreachable():
    source = KERNEL.read_text()
    tree = ast.parse(source)

    # (a) every `outcome=` keyword in the kernel is a LegalOutcome value,
    # never the illegal one.
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            for keyword in node.keywords:
                if keyword.arg == "outcome":
                    value = keyword.value
                    if isinstance(value, ast.Constant):
                        assert value.value != "WaitForHumanToNotice", ast.dump(node)
                    elif isinstance(value, ast.Attribute):
                        assert value.attr != "WAIT_FOR_HUMAN_TO_NOTICE", ast.dump(node)

    # (b) every textual occurrence of the illegal member is inside the
    # IllegalOutcome enum body or the asserted_illegal_outcome property.
    sanctioned: list[tuple[int, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.ClassDef, ast.FunctionDef)) and (
            node.name == "IllegalOutcome"
            or (isinstance(node, ast.FunctionDef) and node.name == "asserted_illegal_outcome")
        ):
            sanctioned.append((node.lineno, node.end_lineno or node.lineno))
    assert sanctioned, "sanctioning scopes not found"
    for lineno, line in enumerate(source.splitlines(), start=1):
        if "WAIT_FOR_HUMAN_TO_NOTICE" in line and "outcome=" not in line:
            inside = any(start <= lineno <= end for start, end in sanctioned)
            assert inside, (
                f"line {lineno} references the illegal outcome outside the "
                f"sanctioned scopes: {line.strip()}"
            )


def test_guard_assisted_to_autonomous_raises_and_others_do_not():
    with pytest.raises(LoopBudgetExceeded):
        EpisodeStanding.transition(EpisodeStanding.ASSISTED, EpisodeStanding.AUTONOMOUS)
    # anti-vacuity for the guard: every non-forbidden transition passes
    for before in EpisodeStanding:
        for after in EpisodeStanding:
            if before is EpisodeStanding.ASSISTED and after is EpisodeStanding.AUTONOMOUS:
                continue
            assert EpisodeStanding.transition(before, after) is after


def test_guard_unnamespaced_receipt_ext_raises():
    fields = dict(
        work_order_id="WO",
        origin_authority={},
        provider={},
        provider_execution_id="pe",
        subject_before={},
        subject_after={},
        commands=[],
        consequences=[],
        evidence=[],
        exit_status="success",
        timestamps={},
        replay_binding={},
    )
    with pytest.raises(LoopBudgetExceeded):
        ExecutionReceipt(**fields, ext={"smuggled": True})
    # anti-vacuity: namespaced ext is admitted
    receipt = ExecutionReceipt(**fields, ext={"aloup.outcome": "Recover"})
    assert receipt.ext == {"aloup.outcome": "Recover"}


def test_guard_scenarios_manifest_entries_exist(court):
    manifest = court.load_manifest()
    ids = {s["id"] for s in manifest["scenarios"]}
    assert ids >= court.GUARD_SCENARIO_IDS


def test_every_loop_receipt_satisfies_the_contract(manifest, scenario, seed, court):
    """Contract conformance on real loop output: every emitted receipt has all
    twelve contract fields populated and only namespaced ext keys; the OCEL
    log referencing it validates."""
    if scenario["id"] in court.GUARD_SCENARIO_IDS:
        pytest.skip("guard scenario emits no receipt")
    built = court.BUILDERS[scenario["id"]](seed, inject=True)
    results = built.run()
    receipts = [r.receipt for r in results if r.receipt is not None]
    if not receipts:
        # a terminal without a receipt is lawful ONLY as Refuse/TypedBlock
        # (zero actuation); anything else would be an unreceipted actuation.
        assert results[-1].outcome in {"Refuse", "TypedBlock"}, (
            f"{scenario['id']}: terminal {results[-1].outcome} with no receipt"
        )
        return
    for receipt in receipts:
        for field_name in REQUIRED_RECEIPT_FIELDS:
            value = getattr(receipt, field_name)
            assert value not in (None, [], {}), (
                f"{scenario['id']}: receipt field {field_name} empty"
            )
        for key in receipt.ext:
            assert "." in key, f"un-namespaced ext key {key!r}"
            assert key.startswith("aloup."), f"foreign ext namespace {key!r}"
        assert receipt.exit_status
        assert receipt.replay_binding.get("provider_execution_id")
    log = loop_log(results, seed=seed)
    validate_ocel_log(log)
