"""Court: every public name `gymact/__init__.py` imports from a `gymact.*` module
is listed in `__all__`, and every `__all__` entry resolves on the real package.

Why: a merge resolution once kept 13 temperament imports but dropped their
`__all__` entries. Only lint noticed. This asserts on the real source (AST) and the
real imported package, not on a hand-maintained list.
"""

from __future__ import annotations

import ast
from pathlib import Path

import gymact

_INIT = Path(gymact.__file__)


def _imported_public_names() -> set[str]:
    tree = ast.parse(_INIT.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("gymact."):
            for alias in node.names:
                bound = alias.asname or alias.name
                if not bound.startswith("_"):
                    names.add(bound)
    return names


def test_every_imported_public_name_is_exported() -> None:
    missing = sorted(_imported_public_names() - set(gymact.__all__))
    assert missing == [], f"imported into gymact/__init__.py but absent from __all__: {missing}"


def test_every_exported_name_resolves_and_is_unique() -> None:
    exported = list(gymact.__all__)
    assert len(exported) == len(set(exported)), "duplicate names in __all__"
    unresolved = [name for name in exported if not hasattr(gymact, name)]
    assert unresolved == [], f"__all__ names that do not resolve: {unresolved}"
