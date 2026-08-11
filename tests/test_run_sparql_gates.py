"""Real, Chicago-style tests for scripts/run_sparql_gates.py.

No mocks: builds real temp pack directories with real .ttl ontologies and
real .rq gate files on disk, runs the real script functions against real
rdflib Graphs, and asserts on the real pass/fail results -- not on "was
rdflib called."
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from run_sparql_gates import (  # noqa: E402
    discover_pack_dirs,
    main,
    parse_gate_source,
    run_all,
    run_pack_gates,
)

_ONTOLOGY_TTL = """
@prefix sosa: <http://www.w3.org/ns/sosa/> .
@prefix dct: <http://purl.org/dc/terms/> .

<urn:test:capability:one> a sosa:Procedure ;
    dct:title "Do the thing" ;
    dct:type <urn:gymact:consequence:do> .
"""

_PASSING_GATE = """# MESSAGE: every capability requires dct:title.
PREFIX sosa: <http://www.w3.org/ns/sosa/>
PREFIX dct: <http://purl.org/dc/terms/>
SELECT ?cap WHERE {
  ?cap a sosa:Procedure .
  FILTER NOT EXISTS { ?cap dct:title ?t }
}
"""

_FAILING_GATE = """# MESSAGE: no sosa:Procedure may exist (deliberately violated for this test).
PREFIX sosa: <http://www.w3.org/ns/sosa/>
SELECT ?cap WHERE {
  ?cap a sosa:Procedure .
}
"""

_ASK_FAILING_GATE = """# MESSAGE: at least one capability must exist (ASK form).
PREFIX sosa: <http://www.w3.org/ns/sosa/>
ASK { ?cap a sosa:Procedure . }
"""


def _write_pack(root: Path, *, gates: dict[str, str], ontology: str | None = _ONTOLOGY_TTL) -> Path:
    pack_dir = root / "sample-pack"
    pack_dir.mkdir(parents=True)
    if ontology is not None:
        (pack_dir / "ontology.ttl").write_text(ontology)
    gates_dir = pack_dir / "gates"
    gates_dir.mkdir()
    for name, content in gates.items():
        (gates_dir / name).write_text(content)
    return pack_dir


def test_parse_gate_source_strips_message_header() -> None:
    message, query = parse_gate_source(_PASSING_GATE)
    assert message == "every capability requires dct:title."
    assert "SELECT ?cap WHERE" in query
    assert not query.startswith("# MESSAGE:")


def test_parse_gate_source_handles_no_header() -> None:
    message, query = parse_gate_source("SELECT ?x WHERE { ?x ?y ?z }")
    assert message is None
    assert query == "SELECT ?x WHERE { ?x ?y ?z }"


def test_run_pack_gates_passes_when_select_returns_no_rows(tmp_path: Path) -> None:
    pack_dir = _write_pack(tmp_path, gates={"010_required.rq": _PASSING_GATE})

    results = run_pack_gates(pack_dir)

    assert len(results) == 1
    assert results[0].passed is True
    assert results[0].pack == "sample-pack"
    assert results[0].gate == "gates/010_required.rq"


def test_run_pack_gates_fails_when_select_returns_a_row(tmp_path: Path) -> None:
    pack_dir = _write_pack(tmp_path, gates={"020_forbidden.rq": _FAILING_GATE})

    results = run_pack_gates(pack_dir)

    assert len(results) == 1
    assert results[0].passed is False
    assert "no sosa:Procedure may exist" in results[0].detail
    assert "SELECT returned 1 row" in results[0].detail


def test_run_pack_gates_fails_when_ask_returns_true(tmp_path: Path) -> None:
    pack_dir = _write_pack(tmp_path, gates={"030_ask.rq": _ASK_FAILING_GATE})

    results = run_pack_gates(pack_dir)

    assert len(results) == 1
    assert results[0].passed is False
    assert "ASK returned true" in results[0].detail


def test_run_pack_gates_mixed_pass_and_fail(tmp_path: Path) -> None:
    pack_dir = _write_pack(
        tmp_path,
        gates={"010_required.rq": _PASSING_GATE, "020_forbidden.rq": _FAILING_GATE},
    )

    results = run_pack_gates(pack_dir)

    assert len(results) == 2
    by_gate = {r.gate: r for r in results}
    assert by_gate["gates/010_required.rq"].passed is True
    assert by_gate["gates/020_forbidden.rq"].passed is False


def test_run_pack_gates_skips_template_pack_with_no_real_ontology(tmp_path: Path) -> None:
    pack_dir = _write_pack(tmp_path, gates={"010_required.rq": _PASSING_GATE}, ontology=None)
    (pack_dir / "ontology.ttl.example").write_text(_ONTOLOGY_TTL)

    results = run_pack_gates(pack_dir)

    assert len(results) == 1
    assert results[0].passed is True
    assert "SKIPPED" in results[0].detail


def test_run_pack_gates_returns_empty_for_pack_with_no_gates_dir(tmp_path: Path) -> None:
    pack_dir = tmp_path / "no-gates-pack"
    pack_dir.mkdir()
    (pack_dir / "ontology.ttl").write_text(_ONTOLOGY_TTL)

    assert run_pack_gates(pack_dir) == []


def test_run_all_aggregates_across_multiple_packs(tmp_path: Path) -> None:
    pack_a = _write_pack(tmp_path / "a", gates={"010_required.rq": _PASSING_GATE})
    pack_b = _write_pack(tmp_path / "b", gates={"020_forbidden.rq": _FAILING_GATE})

    results = run_all([pack_a, pack_b])

    assert len(results) == 2
    assert sum(1 for r in results if r.passed) == 1
    assert sum(1 for r in results if not r.passed) == 1


def test_main_returns_zero_when_all_gates_pass(tmp_path: Path, capsys) -> None:
    pack_dir = _write_pack(tmp_path, gates={"010_required.rq": _PASSING_GATE})

    exit_code = main([str(pack_dir)])

    assert exit_code == 0
    captured = capsys.readouterr()
    assert "1/1 gates passed" in captured.out


def test_main_returns_one_when_any_gate_fails(tmp_path: Path, capsys) -> None:
    pack_dir = _write_pack(tmp_path, gates={"020_forbidden.rq": _FAILING_GATE})

    exit_code = main([str(pack_dir)])

    assert exit_code == 1
    captured = capsys.readouterr()
    assert "[FAIL]" in captured.out


def test_discover_pack_dirs_finds_real_repo_packs() -> None:
    """Real, non-mocked check against this repo's actual ggen/ directory."""
    pack_dirs = discover_pack_dirs()

    names = {p.name for p in pack_dirs}
    assert "gymact-bridge-pack" in names
    assert "togaf-gym-pack" in names
    assert "career-gym-pack" in names


def test_real_repo_gates_all_pass() -> None:
    """The real, load-bearing check: every gate in this repo's actual packs passes.

    This is the same invocation `just ggen-gates-check` runs, exercised
    directly here so a regression in any pack's ontology fails the normal
    test suite too, not only a manual `just` invocation.
    """
    results = run_all(discover_pack_dirs())

    failed = [r for r in results if not r.passed]
    assert failed == [], f"real ggen pack gates failed: {failed}"
    assert len(results) > 0
