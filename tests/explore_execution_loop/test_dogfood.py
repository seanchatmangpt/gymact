"""Dogfood court: the episode attacking its own receipts.

Fixtures under ``fixtures/`` are byte-copies of REAL artifacts written by
concurrent lanes of ALOOP-ZCODE-DOGFOOD-001 (provenance in
``fixtures/README.md``). These tests replay them as real episode inputs:

* lane-1's record: contract-conformance of a real sibling receipt;
* lane-8's validator: structural attack of the cross-lane anti-vacuity
  harness (L8 owns the receipt-normalizer seam);
* lane-10's verdict + run log: a stale-observation claim
  (``real_lane_manifests.files_scanned == 0``) contradicted by the episode
  root's actual contents;
* lane-7's PRIOR incarnation: the manifest claimed deliverables while the
  kernel had never executed (preserved TypeError witness) -- the
  crash-before-receipt fault, witnessed on this lane itself.

Honesty note: all assertions here are against the fixture bytes; where the
ordering of events across lanes is unprovable (clocks are unsynchronized,
several lanes use placeholder timestamps), the test asserts exactly what the
bytes show and no more.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"

EPISODE_STANDINGS = {
    "AUTONOMOUS",
    "ASSISTED",
    "BLOCKED_AUTHORITY",
    "BLOCKED_INFORMATION",
    "FAILED",
}
RESULT_STANDINGS = {
    "ALIVE",
    "PARTIAL_ALIVE",
    "BLOCKED",
    "REFUSED",
    "UNSUPPORTED",
    "UNKNOWN",
}


def _fixture(name: str) -> Path:
    path = FIXTURES / name
    assert path.is_file() and path.stat().st_size > 0, f"fixture missing: {name}"
    return path


# --------------------------------------------------------------------------- #
# lane-1: a real sibling receipt
# --------------------------------------------------------------------------- #


def test_lane1_record_is_contract_conformant():
    record = json.loads(_fixture("lane1_record.json").read_text())
    assert record["episode"] == "ALOOP-ZCODE-DOGFOOD-001"
    assert record["standing"] in EPISODE_STANDINGS
    # standing law: an ASSISTED lane must not claim AUTONOMOUS recurrence
    if record["standing"] == "ASSISTED":
        assert record["recurrence"]["demonstrated"] is False
    # every human causal edge must be pre-epoch (launcher enumeration)
    for edge in record["human_causal_edges"]:
        assert edge["phase"] == "pre-epoch", (
            f"post-epoch human causal edge in lane-1 record: {edge}"
        )
    for receipt in record["receipts"]:
        for field_name in (
            "work_order_id",
            "provider",
            "provider_execution_id",
            "origin_authority",
            "exit_status",
            "replay_binding",
        ):
            assert receipt.get(field_name), (
                f"lane-1 receipt {receipt.get('work_order_id')} missing {field_name}"
            )
    # repos must carry exact identity (start AND final SHA)
    for repo in record["repos"]:
        assert len(repo["start_sha"]) == 40 and len(repo["final_sha"]) == 40
        assert repo["commits"], f"lane-1 repo {repo['repo']} claims no commits"


def test_lane1_falsifiers_are_typed_not_claimed():
    record = json.loads(_fixture("lane1_record.json").read_text())
    for falsifier in record["falsifiers"]:
        assert falsifier["result"] in {"PASS", "FAIL", "NOT_RUN"}
    # honest: some falsifiers were not run, and the record says so
    assert any(f["result"] == "NOT_RUN" for f in record["falsifiers"])


# --------------------------------------------------------------------------- #
# lane-8: cross-lane anti-vacuity harness (receipt-normalizer seam)
# --------------------------------------------------------------------------- #


def test_lane8_validator_harness_is_not_vacuous_by_construction():
    source = _fixture("lane8_validator_antivacuity.py").read_text()
    tree = ast.parse(source)
    appends = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "append"
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "cases"
    ]
    assert len(appends) >= 10, f"lane-8 harness has only {len(appends)} cases"
    refusal_cases = 0
    for node in appends:
        # each case is one Tuple argument: (name, receipt, expect_admit, terms)
        if not node.args or not isinstance(node.args[0], ast.Tuple):
            continue
        elements = node.args[0].elts
        if len(elements) < 4:
            continue
        expect_admit, terms = elements[2], elements[3]
        if isinstance(expect_admit, ast.Constant) and expect_admit.value is False:
            refusal_cases += 1
            # every refusal case names at least one typed term (4th element)
            assert isinstance(terms, (ast.List, ast.Tuple)), (
                "lane-8 refusal case without typed terms"
            )
            assert len(terms.elts) >= 1, "empty typed-term list in refusal case"
    assert refusal_cases >= 5, (
        f"lane-8 harness has {refusal_cases} refusal cases; a validator whose "
        "refusals are not witnessed is vacuous"
    )


# --------------------------------------------------------------------------- #
# lane-10: a stale-observation claim, attacked
# --------------------------------------------------------------------------- #


def test_lane10_verdict_contract_fields():
    verdict = json.loads(_fixture("lane10_verdict.json").read_text())
    assert verdict["overall"] in {"FULL", "PARTIAL", "BLOCKED"}
    assert verdict["anti_vacuity"]["all_mutants_refused"] is True
    assert verdict["anti_vacuity"]["mutant_survivors"] == []
    for mutant in verdict["mutants"]:
        assert mutant["survived"] is False, f"lane-10 mutant {mutant['id']} survived"
        assert mutant["observed_codes"], f"lane-10 mutant {mutant['id']} untyped"


def test_lane10_zero_scan_claim_is_contradicted_by_the_episode_root():
    """lane-10's verdict says ``real_lane_manifests.files_scanned: 0`` with
    reason 'no real lane manifests were available to this run'. The episode
    root demonstrably contained consumable lane manifest artifacts (this
    court's own fixtures are five of them, copied from that root). Ordering
    versus lane-10's scan is NOT provable from the bytes (unsynchronized
    clocks); what IS proven: a scan returning 0 files was, at latest by this
    court's run, contradicted by the directory contents -- the claim is stale
    or the scan was broken, and either way the UNKNOWN verdict rests on it."""
    verdict = json.loads(_fixture("lane10_verdict.json").read_text())
    assert verdict["real_lane_manifests"]["files_scanned"] == 0
    assert verdict["real_lane_manifests"]["verdict"] == "UNKNOWN"

    consumable = [
        "lane1_record.json",
        "lane7_prior_manifest.json",
        "lane8_validator_antivacuity.py",
        "lane10_run.ndjson",
        "lane10_verdict.json",
    ]
    present = 0
    for name in consumable:
        path = _fixture(name)
        path.read_text()  # parseable bytes exist
        present += 1
    assert present == len(consumable)
    # the run log lane-10 emitted is itself a real lane event log -- its own
    # 'no manifests available' reason cannot describe this artifact.
    # WITNESSED DEFECT (2026-09-25): its terminal record is MALFORMED JSON --
    # an unescaped quote inside the blockers string terminates the JSON string
    # early (parse error at char 354), so the lane's own append-only log
    # cannot be replayed cold. Asserted exactly as the bytes show.
    valid, malformed = [], []
    for line in _fixture("lane10_run.ndjson").read_text().splitlines():
        if not line.strip():
            continue
        try:
            valid.append(json.loads(line))
        except json.JSONDecodeError as exc:
            malformed.append((line, exc))
    assert len(valid) >= 3, "lane-10 log: too few parseable records"
    # WITNESSED DEFECT: the first record's notes describe orientation
    # ('first action echo done') but its phase label is 'verify' -- phase
    # labels in the sibling log are unreliable. Asserted as observed.
    assert valid[0]["phase"] == "verify"
    assert valid[0]["notes"].startswith("first action echo done")
    assert malformed, "expected the witnessed malformed terminal record"
    for line, _exc in malformed:
        assert '"phase":"terminal"' in line, (
            "malformed lane-10 record is not the terminal record; re-characterize"
        )
    for entry in valid:
        assert entry["standing"] in EPISODE_STANDINGS | RESULT_STANDINGS, (
            f"lane-10 event uses off-vocabulary standing {entry['standing']!r}"
        )


# --------------------------------------------------------------------------- #
# lane-7 prior incarnation: the crash-before-receipt fault, witnessed
# --------------------------------------------------------------------------- #


def test_prior_lane7_kernel_had_never_executed():
    """The preserved diagnostic proves the prior lane-7 worker died BEFORE the
    kernel's first successful run: TypeError at the very first gate path.
    That is this lane's own crash-before-receipt fault, and it is the reason
    this court exists."""
    witness = _fixture("lane7_prior_typeerror_witness.txt").read_text()
    assert "exit: 3" in witness
    assert "TypeError: AutonomousLoop._resolve_fresh() takes 2 positional arguments but 3 were given" in witness
    assert "_resolve_fresh" in witness


def test_prior_lane7_manifest_claims_are_now_satisfied():
    """The prior incarnation's manifest declared deliverables; the claims were
    O (unverified) at write time. This run manufactures them: the manifest
    file exists, the corpus court exists beside it, and the lifegym
    BLOCKED_INFORMATION recorded then is carried forward unchanged."""
    prior = json.loads(_fixture("lane7_prior_manifest.json").read_text())
    assert prior["repos"]["lifegym"]["status"] == "BLOCKED_INFORMATION"
    court_dir = Path(__file__).parent
    assert (court_dir / "scenario_manifest.json").is_file()
    assert (court_dir / "conftest.py").is_file()
    assert (court_dir / "test_fault_corpus.py").is_file()
    assert (court_dir / "test_antivacuity.py").is_file()
    # the prior manifest's contract must match this court's manifest contract
    current = json.loads((court_dir / "scenario_manifest.json").read_text())
    assert current["contract"]["ExecutionReceipt"] == prior["contract"]["ExecutionReceipt"]
    assert (
        current["repos"]["lifegym"]["status"]
        .startswith(prior["repos"]["lifegym"]["status"])
    )


def test_prior_lane7_kernel_is_now_alive_where_it_crashed(court):
    """The exact path that raised in the prior incarnation (first
    ``run()`` through ``_resolve_fresh``) now completes ALIVE; the
    moving-subject path that held the second latent defect completes too."""
    happy = court.BUILDERS["L7-F13-stale-subject-sha"](7, inject=True).run()[0]
    assert happy.outcome == "Recover" and happy.standing.value == "ALIVE"
    moving = court.BUILDERS["L7-F14-moving-subject-single-move"](7, inject=True).run()[0]
    assert moving.outcome == "Recover" and moving.standing.value == "ALIVE"
