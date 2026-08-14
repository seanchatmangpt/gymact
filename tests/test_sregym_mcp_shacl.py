from pathlib import Path

from pyshacl import validate
from rdflib import Graph

ROOT = Path(__file__).resolve().parent.parent
ONTOLOGY = ROOT / "ggen" / "sregym-e2e-pack" / "ontology.ttl"
SHAPES = ROOT / "ggen" / "sregym-e2e-pack" / "gates" / "sregym-mcp.shacl.ttl"


def test_sregym_mcp_ontology_conforms_to_admission_shapes() -> None:
    data = Graph().parse(ONTOLOGY, format="turtle")
    shapes = Graph().parse(SHAPES, format="turtle")
    conforms, _, report = validate(
        data_graph=data,
        shacl_graph=shapes,
        inference="none",
        advanced=True,
    )
    assert conforms, report
