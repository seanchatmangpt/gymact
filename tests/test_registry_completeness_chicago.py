"""Chicago-style completeness court for every real ``*Provider`` class.

Registration and deliberate exclusion are ontology-owned.  This test mechanically
compares the real source tree against the generated runtime registry and the registry
ABox; it contains no hand-maintained provider allowlist.
"""

from __future__ import annotations

import ast
import importlib
from pathlib import Path

import pytest
from rdflib import Graph, Namespace, RDF

from gymact import registry

ROOT = Path(__file__).resolve().parent.parent
GYMS_ROOT = ROOT / "src" / "gymact" / "gyms"
REGISTRY_ONTOLOGIES = (
    ROOT / "ggen" / "gymact-registry-pack" / "ontology.ttl",
    ROOT / "ggen" / "gymact-registry-pack" / "exclusions.ttl",
)
RG = Namespace("http://seanchatmangpt.github.io/packs/gymact-registry#")


def _registry_graph() -> Graph:
    graph = Graph()
    for path in REGISTRY_ONTOLOGIES:
        graph.parse(path, format="turtle")
    return graph


def _ontology_exclusions() -> dict[str, str]:
    graph = _registry_graph()
    excluded: dict[str, str] = {}
    for subject in graph.subjects(RDF.type, RG.ExcludedProvider):
        qualified = graph.value(subject, RG.excludedClass)
        reason = graph.value(subject, RG.exclusionReason)
        assert qualified is not None, f"excluded provider {subject} lacks rg:excludedClass"
        assert reason is not None and str(reason).strip(), (
            f"excluded provider {subject} lacks a non-empty rg:exclusionReason"
        )
        class_name = str(qualified).rsplit(".", 1)[-1]
        assert class_name not in excluded, f"duplicate excluded provider class: {class_name}"
        excluded[class_name] = str(reason)
    return excluded


def _ontology_registered() -> dict[str, str]:
    graph = _registry_graph()
    registered: dict[str, str] = {}
    for subject in graph.subjects(RDF.type, RG.RegisteredProvider):
        key = graph.value(subject, RG.registryKey)
        class_name = graph.value(subject, RG.providerClassName)
        assert key is not None and class_name is not None
        key_text = str(key)
        assert key_text not in registered, f"duplicate registry key in ontology: {key_text}"
        registered[key_text] = str(class_name)
    return registered


def _real_provider_classes_under_gyms() -> dict[str, Path]:
    """AST-scan real provider declarations without importing optional dependencies."""
    found: dict[str, Path] = {}
    for py_file in sorted(GYMS_ROOT.rglob("*.py")):
        if py_file.name == "__init__.py":
            continue
        tree = ast.parse(py_file.read_text(), filename=str(py_file))
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name.endswith("Provider"):
                assert node.name not in found, (
                    f"duplicate Provider class name {node.name}: {found[node.name]} and {py_file}"
                )
                found[node.name] = py_file
    return found


def test_every_real_gym_provider_class_is_registered_or_ontology_excluded() -> None:
    provider_classes = _real_provider_classes_under_gyms()
    assert provider_classes, "expected real Provider classes under src/gymact/gyms"

    registered_class_names = {cls.__name__ for cls, _caps in registry._BUILTINS.values()}
    excluded_class_names = set(_ontology_exclusions())
    unaccounted = sorted(
        set(provider_classes) - registered_class_names - excluded_class_names
    )
    assert unaccounted == [], (
        "real gym Provider classes lack both registry standing and an ontology exclusion: "
        f"{unaccounted}; source files={ [str(provider_classes[name]) for name in unaccounted] }"
    )


def test_ontology_exclusions_are_real_classes_not_stale_names() -> None:
    provider_classes = _real_provider_classes_under_gyms()
    stale = sorted(set(_ontology_exclusions()) - set(provider_classes))
    assert stale == [], f"ontology exclusions name no real Provider class: {stale}"


def test_ontology_exclusions_and_registry_do_not_overlap() -> None:
    registered_class_names = {cls.__name__ for cls, _caps in registry._BUILTINS.values()}
    overlap = registered_class_names & set(_ontology_exclusions())
    assert overlap == set(), (
        f"Provider classes are simultaneously registered and excluded: {sorted(overlap)}"
    )


def test_generated_registry_exactly_matches_registered_provider_ontology() -> None:
    expected = _ontology_registered()
    observed = {key: provider_type.__name__ for key, (provider_type, _caps) in registry._BUILTINS.items()}
    assert observed == expected


@pytest.mark.parametrize("name", sorted(registry.builtin_provider_names()))
def test_every_registered_builtin_actually_instantiates_and_reports_capabilities(name: str) -> None:
    provider = registry.create_builtin_provider(name)
    capabilities = registry.builtin_capabilities(name)
    assert provider is not None
    assert isinstance(capabilities, tuple)
    assert len(capabilities) >= 1
    described = registry.describe_builtin_provider(name)
    assert described["name"] == name
    assert described["type"] == type(provider).__name__


def test_registered_module_paths_match_real_gyms_tree() -> None:
    provider_classes = _real_provider_classes_under_gyms()
    for cls, _caps in registry._BUILTINS.values():
        module = importlib.import_module(cls.__module__)
        assert getattr(module, cls.__name__) is cls
        if cls.__module__.startswith("gymact.gyms"):
            assert cls.__name__ in provider_classes
