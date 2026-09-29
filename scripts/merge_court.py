#!/usr/bin/env python3
"""Merge court: pre-commit checks for a merge/integration working tree.

Reports (compact JSON on stdout; exit 1 when any check fails, 2 on usage error):
  1. syntax:  Python files under src/ and tests/ that fail ast.parse.
  2. exports: public names imported into src/gymact/__init__.py from gymact.*
     but absent from __all__ (same AST rule as tests/test_public_api_exports_chicago.py,
     which additionally checks the imported package; this court needs no import).
  3. ruff:    real `ruff check` and `ruff format --check` over src and tests.
  4. --branch <ref>: files add/add-conflicting with the current tree (added on both
     sides since the merge-base with different bytes), each classified
     format_equivalent (identical after `ruff format`) or semantic.

--base <ref> limits checks 1 and 3 to Python files changed relative to <ref>.
--root <dir> selects the tree (default: current directory).
Stdlib only; ruff must be on PATH for checks 3 and 4 (absence is a failure).
"""

from __future__ import annotations

import argparse
import ast
import json
import subprocess
import sys
from pathlib import Path

SCAN_DIRS = ("src", "tests")


def _run(cmd: list[str], cwd: Path, stdin: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=cwd, input=stdin, capture_output=True, text=True, check=False)


def _git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return _run(["git", *args], root)


def python_files(root: Path, base: str | None) -> list[Path]:
    """Relative .py paths under SCAN_DIRS; with base, only those changed vs base."""
    if base is None:
        found = [p for d in SCAN_DIRS for p in (root / d).rglob("*.py")]
        return sorted(p.relative_to(root) for p in found)
    diff = _git(root, "diff", "--name-only", "--diff-filter=d", base)
    if diff.returncode != 0:
        raise SystemExit(f"merge_court: git diff against {base!r} failed: {diff.stderr.strip()}")
    names = [n for n in diff.stdout.splitlines() if n.endswith(".py")]
    return sorted(Path(n) for n in names if Path(n).parts[0] in SCAN_DIRS and (root / n).is_file())


def check_syntax(root: Path, files: list[Path]) -> list[dict[str, object]]:
    bad: list[dict[str, object]] = []
    for rel in files:
        try:
            ast.parse((root / rel).read_bytes(), filename=str(rel))
        except (SyntaxError, ValueError) as exc:  # IndentationError subclasses SyntaxError
            bad.append({"file": rel.as_posix(), "error": f"{type(exc).__name__}: {exc}"})
    return bad


def _all_names(tree: ast.Module) -> set[str]:
    names: set[str] = set()
    for node in tree.body:
        targets: list[ast.expr] = []
        value: ast.expr | None = None
        if isinstance(node, ast.Assign):
            targets, value = node.targets, node.value
        elif isinstance(node, (ast.AugAssign, ast.AnnAssign)):
            targets, value = [node.target], node.value
        if any(isinstance(t, ast.Name) and t.id == "__all__" for t in targets) and isinstance(
            value, (ast.List, ast.Tuple)
        ):
            names |= {e.value for e in value.elts if isinstance(e, ast.Constant)}
    return names


def check_exports(root: Path) -> dict[str, object]:
    init = root / "src" / "gymact" / "__init__.py"
    if not init.is_file():
        return {"checked": False, "missing_from_all": []}
    try:
        tree = ast.parse(init.read_text(encoding="utf-8"))
    except SyntaxError:
        return {"checked": False, "missing_from_all": []}  # reported by the syntax check
    imported: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("gymact."):
            imported |= {
                a.asname or a.name for a in node.names if not (a.asname or a.name).startswith("_")
            }
    return {"checked": True, "missing_from_all": sorted(imported - _all_names(tree))}


def check_ruff(root: Path, files: list[Path]) -> dict[str, object]:
    targets = [f.as_posix() for f in files]
    if not targets:
        return {"ok": True, "check": {"returncode": 0}, "format": {"returncode": 0}}
    out: dict[str, object] = {}
    for label, cmd in (
        ("check", ["ruff", "check", "--force-exclude", "--output-format", "concise", *targets]),
        ("format", ["ruff", "format", "--force-exclude", "--check", *targets]),
    ):
        try:
            proc = _run(cmd, root)
        except FileNotFoundError:
            out[label] = {"returncode": 127, "output": ["ruff not found on PATH"]}
            continue
        lines = [ln for ln in (proc.stdout + proc.stderr).splitlines() if ln.strip()]
        out[label] = {"returncode": proc.returncode, "output": lines[:50]}
    out["ok"] = all(v["returncode"] == 0 for v in out.values() if isinstance(v, dict))
    return out


def _blobs(root: Path, ref: str) -> dict[str, str]:
    proc = _git(root, "ls-tree", "-r", ref)
    if proc.returncode != 0:
        raise SystemExit(f"merge_court: cannot read tree {ref!r}: {proc.stderr.strip()}")
    blobs: dict[str, str] = {}
    for line in proc.stdout.splitlines():
        meta, path = line.split("\t", 1)
        blobs[path] = meta.split()[2]
    return blobs


def _formatted(root: Path, ref: str, path: str) -> str | None:
    src = _git(root, "show", f"{ref}:{path}").stdout
    proc = _run(["ruff", "format", "--stdin-filename", path, "-"], root, stdin=src)
    return proc.stdout if proc.returncode == 0 else None


def check_branch(root: Path, branch: str) -> list[dict[str, object]]:
    ours, theirs = _blobs(root, "HEAD"), _blobs(root, branch)
    mb = _git(root, "merge-base", "HEAD", branch)
    base = _blobs(root, mb.stdout.strip()) if mb.returncode == 0 else {}
    conflicts: list[dict[str, object]] = []
    for path in sorted(set(ours) & set(theirs)):
        if path in base or ours[path] == theirs[path]:
            continue  # not add/add, or identical bytes
        if path.endswith(".py"):
            mine, other = _formatted(root, "HEAD", path), _formatted(root, branch, path)
            equivalent = mine is not None and mine == other
        else:
            equivalent = False
        conflicts.append({"file": path, "class": "format_equivalent" if equivalent else "semantic"})
    return conflicts


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--root", type=Path, default=Path.cwd())
    ap.add_argument("--base", help="limit syntax/ruff checks to files changed vs this ref")
    ap.add_argument("--branch", help="classify add/add conflicts against this ref")
    args = ap.parse_args(argv)
    root = args.root.resolve()
    if not root.is_dir():
        print(f"merge_court: --root {root} is not a directory", file=sys.stderr)
        return 2

    files = python_files(root, args.base)
    report: dict[str, object] = {
        "root": str(root),
        "files_checked": len(files),
        "syntax_errors": check_syntax(root, files),
        "exports": check_exports(root),
        "ruff": check_ruff(root, files),
    }
    failed = bool(report["syntax_errors"]) or bool(report["exports"]["missing_from_all"])  # type: ignore[index]
    failed = failed or not report["ruff"]["ok"]  # type: ignore[index]
    if args.branch:
        conflicts = check_branch(root, args.branch)
        report["add_add_conflicts"] = conflicts
        failed = failed or any(c["class"] == "semantic" for c in conflicts)
    report["ok"] = not failed
    print(json.dumps(report, separators=(",", ":"), sort_keys=True))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
