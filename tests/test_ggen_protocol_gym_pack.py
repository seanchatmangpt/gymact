from __future__ import annotations

import re
from pathlib import Path

from rdflib import Graph
from rdflib.namespace import OWL, RDF, RDFS

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / "ggen" / "protocol-gym-pack"
CONSUMER = ROOT / "rust" / "protocol_gym"
_TO = re.compile(r'^to: "([^"]+)"$', re.MULTILINE)


def _targets() -> tuple[str, ...]:
    targets = []
    for template in sorted((PACK / "templates").glob("*.tmpl")):
        match = _TO.search(template.read_text())
        assert match is not None
        targets.append(match.group(1))
    return tuple(targets)


def test_protocol_gym_pack_owns_at_least_ten_normal_outputs() -> None:
    targets = _targets()
    assert len(targets) >= 10
    assert len(targets) == len(set(targets))
    assert all("generated" not in target.lower() for target in targets)
    assert all((CONSUMER / target).is_file() for target in targets)


def test_protocol_gym_consumer_names_canonical_pack_and_ontology() -> None:
    # Not a literal "../../..." path: the installed ggen CLI's config
    # validator refuses any ontology.source/packs.path value containing ".."
    # as path traversal (FM-CONFIG-003) -- ontology.ttl and protocol-gym-pack
    # are real relative symlinks into ../../ggen/protocol-gym-pack instead.
    manifest = (CONSUMER / "ggen.toml").read_text()
    assert 'source = "ontology.ttl"' in manifest
    assert 'protocol-gym-pack = { path = "protocol-gym-pack" }' in manifest
    assert not (CONSUMER / "pack").exists()
    assert (CONSUMER / "ontology.ttl").is_symlink()
    assert (CONSUMER / "protocol-gym-pack").is_symlink()
    assert (CONSUMER / "ontology.ttl").resolve() == PACK / "ontology.ttl"
    assert (CONSUMER / "protocol-gym-pack").resolve() == PACK


def test_protocol_gym_fixture_is_public_vocabulary_abox() -> None:
    graph = Graph().parse(PACK / "ontology.ttl", format="turtle")
    forbidden = {OWL.Class, OWL.ObjectProperty, OWL.DatatypeProperty, RDFS.Class}
    assert not any(kind in forbidden for kind in graph.objects(None, RDF.type))
