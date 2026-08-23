from fractions import Fraction

from gymact.explore_semantic_projection_currentness.converter import Converter
from gymact.explore_semantic_projection_currentness.graph import ConversionGraph
from gymact.explore_semantic_projection_currentness.loss import LossVector
from gymact.explore_semantic_projection_currentness.representation import (
    RepresentationCandidate,
    RepresentationKind,
)
from gymact.explore_semantic_projection_currentness.roundtrip import witness
from gymact.explore_semantic_projection_currentness.semantic_type import SemanticType, TermKind

DIGEST = "a" * 64
SHA = "1" * 40


def fixtures(loss: Fraction = Fraction(0)):
    semantic_type = SemanticType(
        "urn:example:type:Temperature",
        TermKind.LITERAL,
        DIGEST,
        "urn:qudt:unit:K",
    )
    rdf = RepresentationCandidate(
        semantic_type,
        RepresentationKind.RDF_TERM,
        (("lexical", "str"), ("datatype", "iri")),
        True,
        0,
        3,
    )
    ash = RepresentationCandidate(
        semantic_type,
        RepresentationKind.ASH_PROJECTION,
        (("value", "float"), ("unit", "iri")),
        True,
        2,
        1,
    )
    wasm = RepresentationCandidate(
        semantic_type,
        RepresentationKind.WASM_CARRIER,
        (("value", "f64"), ("unit", "u32")),
        True,
        4,
        1,
    )
    edges = (
        Converter("rdf_to_ash", rdf, ash, LossVector(unit=loss), 1),
        Converter("ash_to_rdf", ash, rdf, LossVector(), 1),
        Converter("rdf_to_wasm", rdf, wasm, LossVector(), 2),
        Converter("wasm_to_rdf", wasm, rdf, LossVector(), 2),
    )
    graph = ConversionGraph(edges)
    return (
        semantic_type,
        rdf,
        ash,
        wasm,
        graph,
        witness(graph, rdf, ash),
        witness(graph, rdf, wasm),
    )
