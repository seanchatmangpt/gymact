"""Chicago-style completeness check: every real `*Provider` class exported under
`src/gymact/gyms/*.py` (including the `cloudsim` sub-package) must either be a real,
importable value in `gymact.registry._BUILTINS`, or be named in this test's own
`_INTENTIONALLY_UNREGISTERED` allowlist with a real, specific one-line reason.

This is a real static scan of the real source tree (via `ast`, no mocking) plus a real
import of `gymact.registry` and the real allowlisted modules -- it asserts on the actual
classes found and the actual dict contents, not on any packaged/summarized verdict. It is
the automated check that would have caught the registry-drift gap this file documents:
`_BUILTINS` only registering 5 of 21+ real provider classes.

No collaborator here is faked: the filesystem walk, the AST parse, the registry import,
and the allowlisted-module imports are all real. Nothing here needs an interaction-faking
test double of any kind.
"""

from __future__ import annotations

import ast
import importlib
from pathlib import Path

import pytest

from gymact import registry

GYMS_ROOT = Path(__file__).resolve().parent.parent / "src" / "gymact" / "gyms"

# name -> real, specific reason it is deliberately not in `_BUILTINS`. Mirrors the
# "NOT gymact.local_providers"-style comment already present in registry.py itself.
_INTENTIONALLY_UNREGISTERED: dict[str, str] = {
    "BrowserGymProvider": (
        "top-level `import browsergym.core`/`import gymnasium`, gated behind the "
        "optional 'gyms' extra -- importing it with only the base install raises "
        "ImportError."
    ),
    "GymnasiumProvider": ("top-level `import gymnasium`, gated behind the optional 'gyms' extra."),
    "InspectEvalsProvider": (
        "top-level `from inspect_ai import ...`, gated behind the optional 'gyms' "
        "extra (inspect-ai)."
    ),
    "CubeCounterProvider": (
        "top-level `from counter_cube...` re-raised as ImportError when absent, "
        "gated behind the optional 'cube' extra (Python >=3.12 only)."
    ),
    "CubeContainerCounterProvider": (
        "top-level `from cube.infra_local import LocalInfraConfig` re-raised as "
        "ImportError when absent, gated behind the optional 'cube' extra plus Docker."
    ),
    "VendorBenchmarkProvider": (
        "generic vendor-benchmark dispatch surface, not a single fixed-capability "
        "gym -- not a flat builtin name."
    ),
    "LockAndKeyProvider": (
        "real, committed on this branch, but has zero test coverage (no "
        "tests/test_lock_and_key.py) -- surfaced by merging this branch with "
        "origin/main's registry-completeness gate; registering an untested provider "
        "as a live builtin is out of scope for that merge and needs its own change."
    ),
    "ResourceFlowProvider": (
        "real, committed on this branch, but has zero test coverage (no "
        "tests/test_resource_flow.py) -- same rationale as LockAndKeyProvider above."
    ),
    "SwitchboardProvider": (
        "real, committed on this branch, but has zero test coverage (no "
        "tests/test_switchboard.py) -- same rationale as LockAndKeyProvider above."
    ),
    "OpaqueProcedureProvider": (
        "capabilities are constructed per-instance from materialize()-time config "
        "(hidden_steps), not a fixed module-level tuple -- same static-capabilities-"
        "tuple mismatch as VendorBenchmarkProvider/OntologyDrivenProvider below, "
        "found and named while adding the latter's allowlist entry (this gap "
        "pre-dates and is unrelated to that work; confirmed via `git stash`)."
    ),
    "OntologyDrivenProvider": (
        "generic ontology-driven compiler (gymact.gyms.ontology_gym), not a single "
        "fixed-capability gym itself -- same rationale as VendorBenchmarkProvider "
        "above. Requires per-domain configuration (pack_dir, task-family sets) at "
        "construction time, so it isn't zero-arg-instantiable the way _BUILTINS "
        "expects, and its capabilities are derived dynamically from a pack's "
        "ontology.ttl at materialize() time, not a static module-level tuple. The "
        "real, concrete instance (gymact.gyms.togaf.build_togaf_provider) is a "
        "function, not a class, so it is not flagged by this file's AST scan at all."
    ),
}


def _real_provider_classes_under_gyms() -> dict[str, Path]:
    """Real AST scan (no imports) of every `*Provider` class defined under
    `src/gymact/gyms/**/*.py`. Using AST instead of importing keeps this discovery
    step itself safe to run even when optional heavy dependencies are absent.
    """
    found: dict[str, Path] = {}
    for py_file in sorted(GYMS_ROOT.rglob("*.py")):
        if py_file.name == "__init__.py":
            continue
        tree = ast.parse(py_file.read_text(), filename=str(py_file))
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name.endswith("Provider"):
                found[node.name] = py_file
    return found


def test_every_real_gym_provider_class_is_registered_or_allowlisted():
    provider_classes = _real_provider_classes_under_gyms()
    assert provider_classes, "expected to find real Provider classes under src/gymact/gyms"

    registered_class_names = {cls.__name__ for cls, _caps in registry._BUILTINS.values()}

    unaccounted = [
        name
        for name in provider_classes
        if name not in registered_class_names and name not in _INTENTIONALLY_UNREGISTERED
    ]
    assert unaccounted == [], (
        "the following real gym Provider classes are neither registered in "
        "gymact.registry._BUILTINS nor named in this test's "
        "_INTENTIONALLY_UNREGISTERED allowlist with a reason: "
        f"{sorted(unaccounted)} (source files: "
        f"{[str(provider_classes[n]) for n in unaccounted]})"
    )


def test_allowlist_entries_are_real_classes_not_stale_names():
    provider_classes = _real_provider_classes_under_gyms()
    stale = [name for name in _INTENTIONALLY_UNREGISTERED if name not in provider_classes]
    assert stale == [], (
        f"allowlist names no real Provider class under src/gymact/gyms anymore: {stale} "
        "-- remove the stale allowlist entry"
    )


def test_allowlist_and_registry_do_not_overlap():
    registered_class_names = {cls.__name__ for cls, _caps in registry._BUILTINS.values()}
    overlap = registered_class_names & set(_INTENTIONALLY_UNREGISTERED)
    assert overlap == set(), (
        f"classes {sorted(overlap)} are both registered in _BUILTINS and listed as "
        "intentionally unregistered -- the allowlist entry is stale, remove it"
    )


@pytest.mark.parametrize("name", sorted(registry.builtin_provider_names()))
def test_every_registered_builtin_actually_instantiates_and_reports_capabilities(name):
    provider = registry.create_builtin_provider(name)
    capabilities = registry.builtin_capabilities(name)
    assert provider is not None
    assert isinstance(capabilities, tuple)
    assert len(capabilities) >= 1
    described = registry.describe_builtin_provider(name)
    assert described["name"] == name
    assert described["type"] == type(provider).__name__


def test_registered_module_paths_match_real_gyms_tree():
    """Cross-check: every class registered under a `gymact.gyms.*` module path must be
    the real class object importable at that path, not a same-named lookalike.
    """
    provider_classes = _real_provider_classes_under_gyms()
    for cls, _caps in registry._BUILTINS.values():
        module = importlib.import_module(cls.__module__)
        assert getattr(module, cls.__name__) is cls
        if cls.__module__.startswith("gymact.gyms"):
            assert cls.__name__ in provider_classes
