"""Court: the explore/exploit boundary is machine-checked, not aspirational.

`.claude/rules/explore-exploit.md` says explore work crosses into `gymact` only after
admission. `docs/explore-admission-ledger.json` records one row per top-level
`src/gymact/explore_*` package. This court RECOMPUTES the facts from the real tree with an
AST import scan and compares them to the ledger. It never asserts a hardcoded verdict.

Status vocabulary (this ledger deliberately cannot say ADMITTED; admission needs
falsification, a stable semantic profile, and an agreeing Rust projection):

- UNADMITTED: no production module imports the package.
- PRODUCTION_REACHED: a production module imports it. A named boundary violation, not a
  promotion.

Regenerate the ledger with: python tests/test_explore_admission_ledger_chicago.py --write
"""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
LEDGER = REPO / "docs" / "explore-admission-ledger.json"
PREFIX = "explore_"
STATUSES = {"UNADMITTED", "PRODUCTION_REACHED"}


def discover_packages(src_root: Path) -> dict[str, list[Path]]:
    """Top-level `explore_*` packages (dirs or single modules) under <src_root>/gymact."""
    base = src_root / "gymact"
    found: dict[str, list[Path]] = {}
    for entry in sorted(base.iterdir()):
        if not entry.name.startswith(PREFIX):
            continue
        if entry.is_dir():
            files = sorted(p for p in entry.rglob("*.py"))
            found[entry.name] = files
        elif entry.suffix == ".py":
            found[entry.stem] = [entry]
    return found


def _module_parts(path: Path, src_root: Path) -> list[str]:
    parts = list(path.relative_to(src_root).with_suffix("").parts)
    return parts


def _imported_explore_targets(tree: ast.AST, own_parts: list[str], is_init: bool) -> set[str]:
    """Top-level explore_* package names imported (or dynamically named) by this tree."""
    pkg_parts = own_parts if is_init else own_parts[:-1]
    targets: set[str] = set()

    def note(dotted: list[str]) -> None:
        if len(dotted) >= 2 and dotted[0] == "gymact" and dotted[1].startswith(PREFIX):
            targets.add(dotted[1])

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                note(alias.name.split("."))
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                keep = len(pkg_parts) - (node.level - 1)
                base = pkg_parts[: max(keep, 0)]
            else:
                base = []
            mod = base + (node.module.split(".") if node.module else [])
            note(mod)
            for alias in node.names:
                note([*mod, alias.name])
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            value = node.value
            if value.startswith("gymact." + PREFIX) and all(
                seg.isidentifier() for seg in value.split(".")
            ):
                note(value.split("."))
    return targets


def _scan(root: Path, src_root: Path | None) -> dict[str, dict[str, set[str]]]:
    """Map imported explore package -> importer package/module label -> files."""
    out: dict[str, dict[str, set[str]]] = {}
    for path in sorted(root.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        if src_root is not None:
            parts = _module_parts(path, src_root)
            is_init = parts[-1] == "__init__"
            own = parts[:-1] if is_init else parts
            targets = _imported_explore_targets(tree, parts, is_init)
            label = ".".join(own) if own else "gymact"
            owner = own[1] if len(own) > 1 and own[1].startswith(PREFIX) else None
        else:
            targets = _imported_explore_targets(tree, ["gymact", "__test__"], False)
            label = path.relative_to(root).as_posix()
            owner = None
        for target in targets:
            if owner == target:
                continue
            out.setdefault(target, {}).setdefault(label, set()).add(owner or "")
    return out


def compute_facts(src_root: Path, tests_root: Path) -> list[dict[str, object]]:
    packages = discover_packages(src_root)
    src_imports = _scan(src_root / "gymact", src_root)
    test_imports = _scan(tests_root, None) if tests_root.exists() else {}
    rows: list[dict[str, object]] = []
    for name, files in packages.items():
        loc = sum(len(p.read_text(encoding="utf-8").splitlines()) for p in files)
        production: list[str] = []
        other_explore: list[str] = []
        for label, owners in src_imports.get(name, {}).items():
            if "" in owners:
                production.append(label)
            else:
                other_explore.extend(sorted(owners))
        test_files = sorted(test_imports.get(name, {}))
        production = sorted(set(production))
        rows.append(
            {
                "package": name,
                "kind": "package" if (src_root / "gymact" / name).is_dir() else "module",
                "loc": loc,
                "has_tests": bool(test_files),
                "test_files": test_files,
                "imported_by_production": production,
                "imported_by_other_explore": sorted(set(other_explore)),
                "status": "PRODUCTION_REACHED" if production else "UNADMITTED",
            }
        )
    return rows


def _load_ledger() -> list[dict[str, object]]:
    return json.loads(LEDGER.read_text(encoding="utf-8"))["packages"]


def check_ledger_covers(rows: list[dict[str, object]], packages: set[str]) -> None:
    names = [str(r["package"]) for r in rows]
    assert len(names) == len(set(names)), "duplicate ledger rows"
    assert set(names) - packages == set(), f"stale rows: {sorted(set(names) - packages)}"
    assert packages - set(names) == set(), f"missing rows: {sorted(packages - set(names))}"


def check_row_facts(rows: list[dict[str, object]], recomputed: list[dict[str, object]]) -> None:
    by_name = {str(r["package"]): r for r in rows}
    for fact in recomputed:
        assert str(fact["package"]) in by_name, f"missing rows: {fact['package']}"
        row = by_name[str(fact["package"])]
        for key in (
            "kind",
            "loc",
            "has_tests",
            "test_files",
            "imported_by_production",
            "imported_by_other_explore",
        ):
            assert row[key] == fact[key], (
                f"{fact['package']}.{key}: ledger={row[key]!r} tree={fact[key]!r}"
            )


def check_status_rule(rows: list[dict[str, object]], recomputed: list[dict[str, object]]) -> None:
    by_name = {str(r["package"]): r for r in rows}
    for fact in recomputed:
        assert str(fact["package"]) in by_name, f"missing rows: {fact['package']}"
        row = by_name[str(fact["package"])]
        assert row["status"] in STATUSES, f"{fact['package']}: status {row['status']!r}"
        if fact["imported_by_production"]:
            assert row["status"] == "PRODUCTION_REACHED", (
                f"{fact['package']} has production importers "
                f"{fact['imported_by_production']} but status is {row['status']}"
            )
        else:
            assert row["status"] == "UNADMITTED", f"{fact['package']}: no importer, {row['status']}"


SRC = REPO / "src"
TESTS = REPO / "tests"


def test_every_explore_package_has_exactly_one_fresh_row() -> None:
    check_ledger_covers(_load_ledger(), set(discover_packages(SRC)))


def test_row_facts_equal_recomputed_tree_facts() -> None:
    check_row_facts(_load_ledger(), compute_facts(SRC, TESTS))


def test_production_importer_forces_production_reached_status() -> None:
    check_status_rule(_load_ledger(), compute_facts(SRC, TESTS))


def test_ledger_never_claims_admitted() -> None:
    assert {r["status"] for r in _load_ledger()} <= STATUSES


# --- injectable-root behaviour: the checks must be able to fail ----------------------------


def _mini_tree(tmp_path: Path) -> tuple[Path, Path]:
    src = tmp_path / "src"
    pkg = src / "gymact"
    (pkg / "explore_aaa").mkdir(parents=True)
    (pkg / "explore_aaa" / "__init__.py").write_text("X = 1\n")
    (pkg / "explore_bbb.py").write_text("from gymact.explore_aaa import X\n")
    (pkg / "prod.py").write_text("from . import explore_bbb\n")
    (pkg / "__init__.py").write_text("")
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_aaa.py").write_text("import gymact.explore_aaa\n")
    return src, tests


def test_scan_derives_importers_from_ast_not_names(tmp_path: Path) -> None:
    src, tests = _mini_tree(tmp_path)
    rows = {r["package"]: r for r in compute_facts(src, tests)}
    assert rows["explore_aaa"]["imported_by_production"] == []
    assert rows["explore_aaa"]["imported_by_other_explore"] == ["explore_bbb"]
    assert rows["explore_aaa"]["has_tests"] is True
    assert rows["explore_bbb"]["imported_by_production"] == ["gymact.prod"]
    assert rows["explore_bbb"]["status"] == "PRODUCTION_REACHED"
    assert rows["explore_bbb"]["has_tests"] is False


def test_fake_package_on_disk_without_row_is_detected(tmp_path: Path) -> None:
    src, tests = _mini_tree(tmp_path)
    ledger = compute_facts(src, tests)
    check_ledger_covers(ledger, set(discover_packages(src)))
    (src / "gymact" / "explore_zzz").mkdir()
    (src / "gymact" / "explore_zzz" / "__init__.py").write_text("")
    with pytest.raises(AssertionError, match="missing rows"):
        check_ledger_covers(ledger, set(discover_packages(src)))


def test_stale_row_is_detected(tmp_path: Path) -> None:
    src, tests = _mini_tree(tmp_path)
    ledger = compute_facts(src, tests)
    (src / "gymact" / "explore_bbb.py").unlink()
    with pytest.raises(AssertionError, match="stale rows"):
        check_ledger_covers(ledger, set(discover_packages(src)))


def test_flipped_fact_is_detected(tmp_path: Path) -> None:
    src, tests = _mini_tree(tmp_path)
    recomputed = compute_facts(src, tests)
    ledger = json.loads(json.dumps(recomputed))
    ledger[0]["has_tests"] = not ledger[0]["has_tests"]
    with pytest.raises(AssertionError, match="has_tests"):
        check_row_facts(ledger, recomputed)


def test_unadmitted_row_with_production_importer_is_detected(tmp_path: Path) -> None:
    src, tests = _mini_tree(tmp_path)
    recomputed = compute_facts(src, tests)
    ledger = json.loads(json.dumps(recomputed))
    for row in ledger:
        if row["package"] == "explore_bbb":
            row["status"] = "UNADMITTED"
    with pytest.raises(AssertionError, match="production importers"):
        check_status_rule(ledger, recomputed)


if __name__ == "__main__":
    if "--write" not in sys.argv:
        raise SystemExit("pass --write to regenerate docs/explore-admission-ledger.json")
    facts = compute_facts(SRC, TESTS)
    reached = [r for r in facts if r["status"] == "PRODUCTION_REACHED"]
    doc = {
        "description": (
            "Explore admission ledger. Facts are recomputed by "
            "tests/test_explore_admission_ledger_chicago.py from an AST import scan. "
            "UNADMITTED = no production importer; PRODUCTION_REACHED = a production "
            "(non-explore_*) module imports it, a named boundary violation and not a "
            "promotion. Nothing here is ADMITTED: admission needs falsification, a stable "
            "semantic profile and an agreeing Rust projection, which this ledger cannot "
            "establish."
        ),
        "summary": {
            "packages": len(facts),
            "total_loc": sum(int(r["loc"]) for r in facts),  # type: ignore[call-overload]
            "production_reached": len(reached),
            "with_tests": sum(1 for r in facts if r["has_tests"]),
        },
        "packages": facts,
    }
    LEDGER.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(doc["summary"]))
