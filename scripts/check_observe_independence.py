#!/usr/bin/env python3
"""Coarse, ADVISORY-ONLY static lint for gym ``observe()`` methods with zero
detected real I/O.

This session's direct code audit found gym providers fall into three real
classes for ``observe()`` independence (see
``.claude/rules/actuation-authority.md``'s "observe() must be an independent
read" section):

1. live independent re-query (subprocess/HTTP/filesystem calls each call --
   e.g. ``kubernetes_reconciliation.py``, ``sregym.py``, ``codebase.py``);
2. in-memory dict mutated only by ``actuate()`` (e.g. ``opaque_procedure.py``,
   ``multicloud.py`` -- legitimate for fully-synthetic/simulated worlds with
   no external system to re-query);
3. hybrid (e.g. ``terraform_docker_apply.py`` -- some fields live-requeried,
   others echoed).

This script flags class-(2)-shaped ``observe()`` methods -- SOURCE-level, via
``ast``, not runtime introspection -- so a human reviewer can judge, per
provider, whether the in-memory-only pattern is a legitimate simulated world
or a real bug (lazily caching what should be a live external system).

IMPORTANT -- THIS SCRIPT IS ADVISORY ONLY. It NEVER fails: ``main()`` always
returns 0, regardless of how many providers classify as NO_IO_DETECTED. It is
not a gate, does not block CI, and must never be wired into a build-blocking
check -- classes 2 and 3 above include real, correct code, and only a human
can judge legitimacy per provider.

Scope, stated honestly: a full cross-module call-graph is not attempted.
Detection walks calls in the ``observe()`` method body itself, then follows
``self.<method>(...)`` calls against sibling methods of the *same class* and
bare ``<function>(...)`` calls against top-level functions of the *same
file*, transitively within that same small, closed set (bounded by the
file's own methods/functions -- there are only finitely many, so this always
terminates; e.g. ``kubernetes_reconciliation.py``'s ``observe()`` calls
``self._state()``, which calls the module-level ``_get_pod_json()``, which
shells out via ``subprocess`` -- a real two-hop chain this script does
follow). It does NOT follow calls into another imported module's functions,
another class's methods, or anything reached through an attribute chain
other than ``self.<name>`` -- if the real I/O lives behind one of those, this
script will not see it and will misreport NO_IO_DETECTED. That is a real,
named limitation, not a silent gap.

Usage::

    uv run python scripts/check_observe_independence.py
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

GYMS_DIR = Path(__file__).parent.parent / "src" / "gymact" / "gyms"

# Real, named allowlist of I/O-indicating callables/attribute-access patterns.
# Matched against the *rightmost* attribute/name in a Call's func expression,
# or against a bare Name for `open(`.
_IO_CALL_NAMES = {
    "run",  # subprocess.run
    "Popen",  # subprocess.Popen
    "get",  # httpx.get / requests.get
    "post",  # httpx.post / requests.post
    "put",
    "patch",
    "delete",
    "request",
    "open",  # builtin open(...)
    "rglob",
    "glob",
    "read_text",
    "read_bytes",
    "socket",
}

# Module/attribute roots that make a plain call like `.run(...)` credible as
# real I/O rather than a coincidental in-memory method of the same name --
# checked via the attribute chain's leftmost name when available.
_IO_ROOT_HINTS = {"subprocess", "httpx", "requests", "socket", "Path", "os"}


def _call_root_name(node: ast.expr) -> str | None:
    """Best-effort leftmost identifier of an attribute chain, e.g.
    `subprocess.run(...)` -> "subprocess", `Path(x).read_text()` -> "Path"."""
    while isinstance(node, ast.Attribute):
        node = node.value
    while isinstance(node, ast.Call):
        node = node.func
    if isinstance(node, ast.Name):
        return node.id
    return None


def _is_io_call(call: ast.Call) -> str | None:
    """Return a real, human-readable reason string if `call` looks like I/O,
    else None."""
    func = call.func
    if isinstance(func, ast.Name):
        if func.id == "open":
            return "open(...)"
        return None
    if isinstance(func, ast.Attribute):
        attr = func.attr
        if attr in _IO_CALL_NAMES:
            root = _call_root_name(func.value)
            if attr == "run" and root != "subprocess":
                # Too many unrelated `.run()` methods exist; require the
                # subprocess root to avoid noisy false positives.
                return None
            if attr in {"get", "post", "put", "patch", "delete", "request"} and root not in {
                "httpx",
                "requests",
            }:
                return None
            return f"{root or '?'}.{attr}(...)"
    return None


def _direct_io_reason(body: ast.AST) -> str | None:
    """Walk the direct AST body of `body` and return a real reason string if
    an I/O-indicating call is found, else None. Does not follow any further
    calls -- callers control the one-level-deep helper-following policy."""
    for node in ast.walk(body):
        if isinstance(node, ast.Call):
            reason = _is_io_call(node)
            if reason is not None:
                return reason
    return None


def _self_method_calls(body: ast.AST) -> set[str]:
    """Every `self.<name>(...)` call target found directly in `body`."""
    names: set[str] = set()
    for node in ast.walk(body):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "self"
        ):
            names.add(node.func.attr)
    return names


def _bare_function_calls(body: ast.AST) -> set[str]:
    """Every bare `<name>(...)` call target found directly in `body`."""
    names: set[str] = set()
    for node in ast.walk(body):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            names.add(node.func.id)
    return names


def _method_has_io(
    method: ast.AsyncFunctionDef | ast.FunctionDef,
    class_methods: dict[str, ast.AsyncFunctionDef | ast.FunctionDef],
    module_functions: dict[str, ast.AsyncFunctionDef | ast.FunctionDef],
) -> tuple[bool, str | None]:
    """Classify `method` (observe()): direct I/O in its own body, transitively
    following `self.<method>()` and bare `<function>()` calls within the same
    closed, finite set of this class's methods + this file's top-level
    functions -- see module docstring's "Scope" section. Bounded by
    `visited`, so this always terminates even with mutual recursion."""
    visited: set[tuple[str, str]] = set()
    queue: list[tuple[ast.AST, str]] = [(method, "observe()")]

    while queue:
        body, chain_label = queue.pop(0)
        reason = _direct_io_reason(body)
        if reason is not None:
            return True, f"{chain_label} -> {reason}" if chain_label != "observe()" else reason

        for helper_name in _self_method_calls(body):
            key = ("self", helper_name)
            if key in visited:
                continue
            visited.add(key)
            helper = class_methods.get(helper_name)
            if helper is None or helper is method:
                continue
            queue.append((helper, f"{chain_label} -> self.{helper_name}()"))

        for func_name in _bare_function_calls(body):
            key = ("fn", func_name)
            if key in visited:
                continue
            visited.add(key)
            func = module_functions.get(func_name)
            if func is None:
                continue
            queue.append((func, f"{chain_label} -> {func_name}()"))

    return False, None


def _find_environment_classes(tree: ast.Module) -> list[ast.ClassDef]:
    return [
        node
        for node in ast.iter_child_nodes(tree)
        if isinstance(node, ast.ClassDef) and node.name.endswith("Environment")
    ]


def check_file(path: Path) -> list[dict[str, object]]:
    """Real AST-level classification of every observe() method found in one
    real gym source file. Returns one dict per (Environment class, observe)
    pair found -- may be empty if the file defines no *Environment class with
    an observe() method."""
    source = path.read_text()
    tree = ast.parse(source, filename=str(path))

    module_functions: dict[str, ast.AsyncFunctionDef | ast.FunctionDef] = {
        node.name: node
        for node in ast.iter_child_nodes(tree)
        if isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef))
    }

    results: list[dict[str, object]] = []
    for class_node in _find_environment_classes(tree):
        class_methods: dict[str, ast.AsyncFunctionDef | ast.FunctionDef] = {
            item.name: item
            for item in class_node.body
            if isinstance(item, (ast.AsyncFunctionDef, ast.FunctionDef))
        }
        observe = class_methods.get("observe")
        if observe is None:
            continue
        has_io, reason = _method_has_io(observe, class_methods, module_functions)
        results.append(
            {
                "file": str(path),
                "class": class_node.name,
                "has_io": has_io,
                "reason": reason,
            }
        )
    return results


def build_report(gyms_dir: Path = GYMS_DIR) -> list[dict[str, object]]:
    """Real, deterministic (sorted-by-file) report across every real
    `src/gymact/gyms/*.py` file."""
    all_results: list[dict[str, object]] = []
    for path in sorted(gyms_dir.glob("*.py")):
        if path.name == "__init__.py":
            continue
        all_results.extend(check_file(path))
    return all_results


def render_report(results: list[dict[str, object]]) -> str:
    lines = [
        "check_observe_independence: ADVISORY ONLY -- never fails, never "
        "blocks CI. Detection scope: observe()'s own body plus transitive "
        "self.<method>()/bare-function() calls within the same file only "
        "(no cross-module call-graph following).",
        "",
    ]
    for entry in results:
        label = "HAS_IO" if entry["has_io"] else "NO_IO_DETECTED"
        reason = f" ({entry['reason']})" if entry.get("reason") else ""
        advisory = (
            ""
            if entry["has_io"]
            else " -- advisory: verify this provider models a genuinely "
            "simulated/synthetic world, not a real external system's cache"
        )
        lines.append(f"{label:16s} {entry['class']:40s} {entry['file']}{reason}{advisory}")
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    results = build_report()
    print(render_report(results))
    return 0  # ADVISORY ONLY -- this script must never fail CI.


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
