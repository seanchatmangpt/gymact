from __future__ import annotations

import re
from pathlib import Path

from rdflib import Graph, URIRef
from rdflib.namespace import OWL, RDF, RDFS

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / "ggen" / "world-cyber-gym-pack"
LOCAL = "urn:gymact:world-cyber:"
_TO = re.compile(r'^to: "([^"]+)"$', re.MULTILINE)


def graph() -> Graph:
    return Graph().parse(PACK / "ontology.ttl", format="turtle")


def test_public_ontology_abox_has_no_local_tbox_or_predicates() -> None:
    g = graph()
    forbidden = {OWL.Class, OWL.ObjectProperty, OWL.DatatypeProperty, RDFS.Class, RDF.Property}
    assert [
        subject
        for subject in g.subjects(RDF.type, None)
        if str(subject).startswith(LOCAL)
        and any((subject, RDF.type, kind) in g for kind in forbidden)
    ] == []
    assert {predicate for _, predicate, _ in g if str(predicate).startswith(LOCAL)} == set()


def test_admitted_graph_passes_world_contract_gate() -> None:
    rows = list(graph().query((PACK / "gates" / "010_world_contract.rq").read_text()))
    assert rows == []


def test_gate_refuses_non_synthetic_disturbance() -> None:
    g = graph()
    cap = URIRef(f"{LOCAL}cap:degrade-service")
    profile = URIRef(f"{LOCAL}profile:synthetic-only")
    dct_conforms = URIRef("http://purl.org/dc/terms/conformsTo")
    g.remove((cap, dct_conforms, profile))
    rows = list(g.query((PACK / "gates" / "010_world_contract.rq").read_text()))
    assert any(str(problem) == "disturbance-not-synthetic-only" for _, problem in rows)


def test_ggen_targets_are_static_cross_language_projections_only() -> None:
    targets = []
    for template in sorted((PACK / "templates").glob("*.tmpl")):
        match = _TO.search(template.read_text())
        assert match is not None
        targets.append(match.group(1))
    assert sorted(targets) == [
        "docs/compiled-reference.md",
        "src/lib.rs",
        "wit/gymact-world-cyber.wit",
    ]
    assert all(not target.endswith(".py") for target in targets)
    combined = "\n".join(path.read_text() for path in (PACK / "templates").glob("*.tmpl"))
    assert "arbitrary-target" in combined
    assert "export catalog" in combined


# Same pinned toolchain capsule already used by the TOGAF ggen court.
_GGEN_URL = (
    "https://github.com/seanchatmangpt/ggen/releases/download/v26.8.8/"
    "ggen-x86_64-unknown-linux-gnu.tar.gz"
)
_GGEN_SHA256 = "c651d873c2aeb6bd71c3d5356634f0b3f4adafd2454ee354c817a7079c2ea802"


def _temporary_consumer(tmp_path: Path) -> Path:
    import os
    import shutil

    workspace = tmp_path / "workspace"
    pack_copy = workspace / "ggen" / "world-cyber-gym-pack"
    consumer = workspace / "rust" / "world_cyber_gym"
    pack_copy.parent.mkdir(parents=True)
    consumer.mkdir(parents=True)
    shutil.copytree(PACK, pack_copy)
    (consumer / "templates").mkdir()
    os.symlink("../../ggen/world-cyber-gym-pack/ontology.ttl", consumer / "ontology.ttl")
    os.symlink("../../ggen/world-cyber-gym-pack", consumer / "world-cyber-gym-pack")
    (consumer / "ggen.toml").write_text(
        '[project]\n'
        'name = "gymact-world-cyber-gym"\n\n'
        '[ontology]\n'
        'source = "ontology.ttl"\n\n'
        '[packs]\n'
        'world-cyber-gym-pack = { path = "world-cyber-gym-pack" }\n\n'
        '[templates]\n'
        'dir = "templates"\n'
    )
    return consumer


def _assert_generated(consumer: Path) -> None:
    assert (consumer / "src" / "lib.rs").is_file()
    assert (consumer / "wit" / "gymact-world-cyber.wit").is_file()
    assert (consumer / "docs" / "compiled-reference.md").is_file()
    rust = (consumer / "src" / "lib.rs").read_text()
    assert "identity-core" in rust
    assert "interrupt-identity" in rust
    wit = (consumer / "wit" / "gymact-world-cyber.wit").read_text()
    assert "export catalog" in wit
    assert "socket" in wit  # only in the explicit prohibition comment
    assert "http-client" not in wit


def test_installed_ggen_manufactures_static_world_cyber_projection(tmp_path: Path) -> None:
    import shutil
    import subprocess

    if shutil.which("ggen") is None:
        import pytest

        pytest.skip("no `ggen` binary found on PATH for local execution")
    consumer = _temporary_consumer(tmp_path)
    result = subprocess.run(
        ["ggen", "sync", "run"], cwd=consumer, capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr
    _assert_generated(consumer)
    receipt = consumer / ".ggen-v2" / "receipt.json"
    assert receipt.is_file() and receipt.stat().st_size > 0


def test_pinned_ggen_v26_8_8_manufactures_on_ci_313(tmp_path: Path) -> None:
    import hashlib
    import os
    import stat
    import subprocess
    import sys
    import tarfile
    import urllib.request

    import pytest

    if os.environ.get("GITHUB_ACTIONS") != "true" or sys.version_info[:2] != (3, 13):
        pytest.skip("pinned ggen toolchain capsule executes on the GitHub Python 3.13 leg")

    archive = tmp_path / "ggen.tar.gz"
    urllib.request.urlretrieve(_GGEN_URL, archive)
    assert hashlib.sha256(archive.read_bytes()).hexdigest() == _GGEN_SHA256
    toolchain = tmp_path / "toolchain"
    toolchain.mkdir()
    with tarfile.open(archive, "r:gz") as tar:
        tar.extractall(toolchain, filter="data")
    executables = [path for path in toolchain.rglob("ggen") if path.is_file()]
    assert len(executables) == 1
    executable = executables[0]
    executable.chmod(executable.stat().st_mode | stat.S_IXUSR)

    consumer = _temporary_consumer(tmp_path)
    subprocess.run([str(executable), "sync", "run"], cwd=consumer, check=True)
    _assert_generated(consumer)
    receipt = consumer / ".ggen-v2" / "receipt.json"
    assert receipt.is_file() and receipt.stat().st_size > 0
