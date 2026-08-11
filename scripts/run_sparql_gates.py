#!/usr/bin/env python3
"""Run every ggen pack's ``gates/*.rq`` SPARQL gate against its own ontology.

This is a read-only verification tool, not a code generator: it does not
require the external ``ggen`` binary (unlike ``just ggen-bridge-check``), only
``rdflib`` (already a core gymact dependency, used throughout
``gymact.semantic``/``gymact.ocel``). It closes a real, named gap found during
the 2026-08-11 ggen-pack review: every pack under ``ggen/*/gates/*.rq`` is
real, checked-in, semantically-reviewed SPARQL, but nothing in this repo
executes any of it -- a human would otherwise have to hand-run ``ggen sync
run`` (which requires the external binary) to exercise these gates at all.

Gate contract, matched exactly to the real ``ggen`` engine's own
``evaluate_gate`` (``~/ggen/crates/ggen-engine/src/sync.rs``, confirmed by
direct reading during the same review):

- ``ASK`` query returning ``true``  -> violation ("ASK returned true").
- ``SELECT`` query returning any row -> violation (one row = one violation).
- Empty ``SELECT`` result           -> pass.
- ``CONSTRUCT``/``DESCRIBE``        -> not a gate query, refused.

Every ``.rq`` file may start with a ``# MESSAGE: ...`` header line (the same
convention ``ggen``'s own ``parse_gate_source`` uses) giving the human-facing
reason for the gate; that header is not part of the query and is stripped
before execution.

Usage::

    uv run python scripts/run_sparql_gates.py            # all packs under ggen/
    uv run python scripts/run_sparql_gates.py ggen/togaf-gym-pack ggen/career-gym-pack

Exits 0 if every gate in every checked pack passes, 1 otherwise.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

from rdflib import Graph

REPO_ROOT = Path(__file__).resolve().parents[1]
GGEN_ROOT = REPO_ROOT / "ggen"

_MESSAGE_PREFIX = "# MESSAGE:"


@dataclass(frozen=True)
class GateResult:
    pack: str
    gate: str
    passed: bool
    detail: str


def parse_gate_source(src: str) -> tuple[str | None, str]:
    """Split an optional leading ``# MESSAGE: ...`` header from the query body.

    Mirrors ggen's own ``parse_gate_source`` convention: only the first line
    is treated as a header, and only when it starts with ``# MESSAGE:``.
    """
    lines = src.splitlines()
    if lines and lines[0].strip().startswith(_MESSAGE_PREFIX):
        message = lines[0].strip()[len(_MESSAGE_PREFIX) :].strip()
        return message, "\n".join(lines[1:])
    return None, src


def evaluate_gate(graph: Graph, query: str) -> tuple[bool, str]:
    """Evaluate one gate query against ``graph``.

    Returns ``(passed, detail)``. Matches ggen's real ``evaluate_gate``
    contract: ASK->true is a violation, SELECT->any row is a violation
    (empty = pass), CONSTRUCT/DESCRIBE are refused as not-a-gate.
    """
    result = graph.query(query)
    if result.type == "ASK":
        value = bool(result.askAnswer)
        if value:
            return False, "ASK returned true"
        return True, ""
    if result.type == "SELECT":
        rows = list(result)
        if not rows:
            return True, ""
        first_repr = str(rows[0])
        return False, f"SELECT returned {len(rows)} row(s); first row: {first_repr}"
    return False, f"NOT_A_GATE: query type {result.type!r} is not ASK or SELECT"


def _load_pack_graph(pack_dir: Path) -> Graph | None:
    """Load a pack's ontology into a Graph, or None if it has no real ontology.

    Handles both the flat ``ontology.ttl`` convention and the split
    ``ontology/*.ttl`` convention (e.g. gymact-bridge-pack's symlinked
    profile.ttl/profile.shacl.ttl). Packs shipping only a
    ``*.ttl.example`` template (e.g. consumer-bridge-pack-template) have no
    real ontology to gate and are skipped, not failed.
    """
    graph = Graph()
    loaded_any = False

    flat = pack_dir / "ontology.ttl"
    if flat.is_file():
        graph.parse(flat, format="turtle")
        loaded_any = True

    split_dir = pack_dir / "ontology"
    if split_dir.is_dir():
        for ttl_file in sorted(split_dir.glob("*.ttl")):
            graph.parse(ttl_file, format="turtle")
            loaded_any = True

    if not loaded_any:
        return None
    return graph


def run_pack_gates(pack_dir: Path) -> list[GateResult]:
    """Run every ``gates/*.rq`` file in ``pack_dir`` against its own ontology."""
    gates_dir = pack_dir / "gates"
    if not gates_dir.is_dir():
        return []

    graph = _load_pack_graph(pack_dir)
    pack_name = pack_dir.name
    if graph is None:
        return [
            GateResult(
                pack=pack_name,
                gate=str(gate_file.relative_to(pack_dir)),
                passed=True,
                detail="SKIPPED: no ontology.ttl or ontology/*.ttl (template pack)",
            )
            for gate_file in sorted(gates_dir.glob("*.rq"))
        ]

    results: list[GateResult] = []
    for gate_file in sorted(gates_dir.glob("*.rq")):
        source = gate_file.read_text()
        message, query = parse_gate_source(source)
        try:
            passed, detail = evaluate_gate(graph, query)
        except Exception as exc:  # real SPARQL parse/eval errors surface as failures
            passed, detail = False, f"QUERY_ERROR: {exc}"
        if not passed and message:
            detail = f"{message} -- {detail}" if detail else message
        results.append(
            GateResult(
                pack=pack_name,
                gate=str(gate_file.relative_to(pack_dir)),
                passed=passed,
                detail=detail,
            )
        )
    return results


def run_all(pack_dirs: list[Path]) -> list[GateResult]:
    results: list[GateResult] = []
    for pack_dir in pack_dirs:
        results.extend(run_pack_gates(pack_dir))
    return results


def discover_pack_dirs() -> list[Path]:
    return sorted(p for p in GGEN_ROOT.iterdir() if p.is_dir() and (p / "gates").is_dir())


def main(argv: list[str]) -> int:
    if argv:
        pack_dirs = [Path(arg).resolve() for arg in argv]
    else:
        pack_dirs = discover_pack_dirs()

    results = run_all(pack_dirs)

    if not results:
        print("run_sparql_gates: no gates found to run.")
        return 0

    failed = [r for r in results if not r.passed]
    for result in results:
        status = "PASS" if result.passed else "FAIL"
        line = f"[{status}] {result.pack}/{result.gate}"
        if result.detail:
            line += f" -- {result.detail}"
        print(line)

    print()
    print(f"{len(results) - len(failed)}/{len(results)} gates passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
