from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
import tarfile
import tomllib
import urllib.request
from pathlib import Path

import pytest
from rdflib import Graph, Namespace, URIRef
from rdflib.namespace import OWL, RDF, RDFS, SKOS

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / "ggen" / "togaf-gym-pack"
COURTS = PACK / "courts" / "shapes.ttl"
PPLAN = Namespace("http://purl.org/net/p-plan#")
PROV = Namespace("http://www.w3.org/ns/prov#")
DCT = Namespace("http://purl.org/dc/terms/")
PROF = Namespace("http://www.w3.org/ns/dx/prof/")
ORG = Namespace("http://www.w3.org/ns/org#")
OSLC_RM = Namespace("http://open-services.net/ns/rm#")
ODRL = Namespace("http://www.w3.org/ns/odrl/2/")
SH = Namespace("http://www.w3.org/ns/shacl#")
EARL = Namespace("http://www.w3.org/ns/earl#")
LOCAL = "urn:gymact:togaf:"
PROFILE = URIRef(f"{LOCAL}profile")
PHASE_SCHEME = URIRef(f"{LOCAL}scheme:adm-phase")
TASK_SCHEME = URIRef(f"{LOCAL}scheme:task-family")

_EXPECTED_PHASES = {
    "Preliminary",
    "Requirements",
    "A",
    "B",
    "C",
    "D",
    "E",
    "F",
    "G",
    "H",
}
_EXPECTED_TASKS = {
    "togaf.00.preliminary",
    "togaf.01.requirements",
    "togaf.10.phase-a",
    "togaf.20.phase-b",
    "togaf.30.phase-c",
    "togaf.40.phase-d",
    "togaf.50.phase-e",
    "togaf.60.phase-f",
    "togaf.70.phase-g",
    "togaf.80.phase-h",
}
_EXPECTED_TARGETS = (
    "consumer/togaf-gym/src/lib.rs",
    "consumer/togaf-gym/wit/gymact-togaf-gym.wit",
    "consumer/togaf-gym/docs/compiled-reference.md",
)
_GGEN_URL = (
    "https://github.com/seanchatmangpt/ggen/releases/download/v26.8.8/"
    "ggen-x86_64-unknown-linux-gnu.tar.gz"
)
_GGEN_SHA256 = "c651d873c2aeb6bd71c3d5356634f0b3f4adafd2454ee354c817a7079c2ea802"


def _data_graph() -> Graph:
    return Graph().parse(PACK / "ontology.ttl", format="turtle")


def _combined_graph() -> Graph:
    graph = _data_graph()
    graph.parse(COURTS, format="turtle")
    return graph


def _gate_rows(graph: Graph, name: str) -> list[tuple[object, ...]]:
    query = (PACK / "gates" / name).read_text()
    return [tuple(row) for row in graph.query(query)]


def _config() -> dict[str, object]:
    with (PACK / "ggen.toml").open("rb") as stream:
        return tomllib.load(stream)


def _ggen_binary(tmp_path: Path) -> Path:
    supplied = os.environ.get("GGEN_BIN")
    if supplied:
        executable = Path(supplied).resolve()
        assert executable.is_file(), executable
        return executable

    if os.environ.get("GITHUB_ACTIONS") != "true" or sys.version_info[:2] != (3, 13):
        pytest.skip("set GGEN_BIN locally; CI downloads the pinned ggen toolchain on Python 3.13")

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
    return executable


def test_togaf_alignment_is_public_vocabulary_abox() -> None:
    graph = _combined_graph()
    forbidden = {OWL.Class, OWL.ObjectProperty, OWL.DatatypeProperty, RDFS.Class, RDF.Property}
    leaked_tbox = [
        term
        for term in graph.subjects(RDF.type, None)
        if str(term).startswith(LOCAL)
        and any((term, RDF.type, kind) in graph for kind in forbidden)
    ]
    local_predicates = {predicate for _, predicate, _ in graph if str(predicate).startswith(LOCAL)}
    assert leaked_tbox == []
    assert local_predicates == set()


def test_profile_reuses_public_ontology_stack() -> None:
    graph = _data_graph()
    expected = {
        URIRef("http://www.w3.org/ns/prov#"),
        URIRef("http://www.w3.org/ns/org#"),
        URIRef("http://www.w3.org/2004/02/skos/core#"),
        URIRef("http://purl.org/net/p-plan#"),
        URIRef("http://open-services.net/ns/rm#"),
        URIRef("http://www.w3.org/ns/dcat#"),
        URIRef("http://www.w3.org/ns/odrl/2/"),
    }
    assert (PROFILE, RDF.type, PROF.Profile) in graph
    assert set(graph.objects(PROFILE, PROF.isProfileOf)) == expected


def test_exact_adm_phase_and_task_coverage() -> None:
    graph = _combined_graph()
    phases = {
        str(notation)
        for phase in graph.subjects(SKOS.inScheme, PHASE_SCHEME)
        for notation in graph.objects(phase, SKOS.notation)
    }
    tasks = {
        str(identifier)
        for task in graph.subjects(RDF.type, PPLAN.Plan)
        for identifier in graph.objects(task, DCT.identifier)
    }
    assert phases == _EXPECTED_PHASES
    assert tasks == _EXPECTED_TASKS


def test_tasks_bind_phase_family_and_shacl_oracle() -> None:
    graph = _combined_graph()
    for task in graph.subjects(RDF.type, PPLAN.Plan):
        phase = list(graph.objects(task, PROV.wasDerivedFrom))
        family = list(graph.objects(task, DCT.type))
        oracle = list(graph.objects(task, DCT.requires))
        assert len(phase) == len(family) == len(oracle) == 1
        assert (phase[0], SKOS.inScheme, PHASE_SCHEME) in graph
        assert (family[0], SKOS.inScheme, TASK_SCHEME) in graph
        assert (oracle[0], RDF.type, SH.NodeShape) in graph
        assert (oracle[0], RDF.type, EARL.TestCriterion) in graph


def test_requirements_use_oslc_rm_traceability() -> None:
    graph = _combined_graph()
    requirements = list(graph.subjects(RDF.type, OSLC_RM.Requirement))
    assert len(requirements) == 4
    for requirement in requirements:
        assert list(graph.objects(requirement, OSLC_RM.specifiedBy))
        assert list(graph.objects(requirement, OSLC_RM.validatedBy))


def test_governance_uses_org_and_odrl() -> None:
    graph = _combined_graph()
    assert (
        URIRef(f"{LOCAL}org:architecture-office"),
        RDF.type,
        ORG.OrganizationalUnit,
    ) in graph
    policy = URIRef(f"{LOCAL}policy:governance")
    assert (policy, RDF.type, ODRL.Set) in graph
    assert list(graph.objects(policy, ODRL.permission))


@pytest.mark.parametrize(
    "gate",
    ["010_no_custom_tbox.rq", "020_adm_phase_set.rq", "030_projection_contract.rq"],
)
def test_admitted_graph_passes_all_sparql_gates(gate: str) -> None:
    assert _gate_rows(_combined_graph(), gate) == []


def test_gates_refuse_semantic_regressions() -> None:
    graph = _combined_graph()
    bad_class = URIRef(f"{LOCAL}BrokenClass")
    graph.add((bad_class, RDF.type, OWL.Class))
    assert _gate_rows(graph, "010_no_custom_tbox.rq")

    graph = _combined_graph()
    phase = URIRef(f"{LOCAL}phase:h")
    graph.remove((phase, SKOS.notation, None))
    assert _gate_rows(graph, "020_adm_phase_set.rq")

    graph = _combined_graph()
    task = URIRef(f"{LOCAL}task:a")
    graph.remove((task, DCT.title, None))
    assert _gate_rows(graph, "030_projection_contract.rq")



def test_ggen_manifest_is_self_contained_and_projection_only() -> None:
    config = _config()
    ontology = config["ontology"]
    assert ontology["source"] == "ontology.ttl"
    assert ontology["imports"] == ["courts/shapes.ttl"]
    assert ".." not in ontology["source"]
    assert all(".." not in path for path in ontology["imports"])

    rules = config["generation"]["rules"]
    targets = tuple(rule["output_file"] for rule in rules)
    assert targets == _EXPECTED_TARGETS
    assert len(targets) == len(set(targets))
    assert all("generated" not in target.lower() for target in targets)
    assert all(not (PACK / target).exists() for target in targets)
    templates = (PACK / "templates").glob("*.tmpl")
    assert all(not template.read_text().startswith("---") for template in templates)
    assert not (PACK / "shapes.ttl").exists()



def test_ggen_v26_8_8_manufactures_ephemeral_projection_and_receipt(tmp_path: Path) -> None:
    executable = _ggen_binary(tmp_path)
    version = subprocess.run(
        [str(executable), "--version"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert version == "ggen 26.8.8"

    pack_copy = tmp_path / "togaf-gym-pack"
    shutil.copytree(PACK, pack_copy)

    shacl = subprocess.run(
        [
            str(executable),
            "graph",
            "validate",
            "--files",
            "ontology.ttl",
            "--shapes",
            "courts/shapes.ttl",
        ],
        cwd=pack_copy,
        check=True,
        capture_output=True,
        text=True,
    )
    assert '"shapes_conform": true' in shacl.stdout

    negative = Graph().parse(pack_copy / "ontology.ttl", format="turtle")
    requirement = URIRef(f"{LOCAL}req:continuity")
    negative.remove((requirement, OSLC_RM.specifiedBy, None))
    negative.serialize(pack_copy / "invalid-requirement.ttl", format="turtle")
    refused = subprocess.run(
        [
            str(executable),
            "graph",
            "validate",
            "--files",
            "invalid-requirement.ttl",
            "--shapes",
            "courts/shapes.ttl",
        ],
        cwd=pack_copy,
        capture_output=True,
        text=True,
    )
    assert refused.returncode != 0
    assert "SHACL validation failed" in refused.stderr
    (pack_copy / "invalid-requirement.ttl").unlink()

    first = subprocess.run(
        [str(executable), "sync", "run"],
        cwd=pack_copy,
        check=True,
        capture_output=True,
        text=True,
    )
    assert '"graph_hash_hex"' in first.stdout
    first_outputs = {
        target: (pack_copy / target).read_bytes() for target in _EXPECTED_TARGETS
    }
    first_receipt = json.loads((pack_copy / ".ggen-v2/receipt.json").read_text())

    second = subprocess.run(
        [str(executable), "sync", "run"],
        cwd=pack_copy,
        check=True,
        capture_output=True,
        text=True,
    )
    assert '"graph_hash_hex"' in second.stdout
    for target in _EXPECTED_TARGETS:
        assert (pack_copy / target).is_file()
        assert (pack_copy / target).read_bytes() == first_outputs[target]

    receipt = pack_copy / ".ggen-v2" / "receipt.json"
    assert receipt.is_file() and receipt.stat().st_size > 0
    second_receipt = json.loads(receipt.read_text())
    for observed in (first_receipt, second_receipt):
        assert observed["record"]["schema"] == "ggen-receipt/v2"
        assert observed["record"]["v2"]["standing_ceiling"] == "Green"
        assert observed["payload"]["closure"]["actuator"] == "ggen@26.8.8"

    # Replay preserves admitted graph, closure, and artifact bytes while the receipt
    # chain records that the second actuation skipped unchanged projections.
    assert first_receipt["payload"]["graph_hash"] == second_receipt["payload"]["graph_hash"]
    assert first_receipt["payload"]["closure"] == second_receipt["payload"]["closure"]
    assert first_receipt["payload"]["outputs"] == second_receipt["payload"]["outputs"]
    assert set(first_receipt["payload"]["decisions"].values()) == {"written"}
    assert all(
        decision.startswith("skipped: unchanged")
        for decision in second_receipt["payload"]["decisions"].values()
    )
    assert (
        second_receipt["record"]["prev_chain_hash_hex"]
        == first_receipt["record"]["chain_hash_hex"]
    )
    assert second_receipt["record"]["v2"]["equivalence"]["source"] == "Equivalent"
    assert second_receipt["record"]["v2"]["equivalence"]["config"] == "Equivalent"

    generated = (pack_copy / "consumer/togaf-gym/src/lib.rs").read_text()
    assert generated.count("ArchitectureTask {") == 11
    assert "togaf.80.phase-h" in generated
    assert generated.count("AdmPhase {") == 11
