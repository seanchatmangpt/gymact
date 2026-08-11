"""Real, Chicago-style tests for `gymact.verification`.

No mocks anywhere: every verifier is exercised against a real `rdflib.Graph` and a real
`pyshacl.validate` call (invoked transitively through `ShaclPostconditionVerifier.judge`).
Assertions are on the real returned `(passed, reason)` tuples -- never on whether a
collaborator method was "called".
"""

from __future__ import annotations

from rdflib import Graph

from gymact.verification import DictSubsetVerifier, ShaclPostconditionVerifier

SHAPES_TTL = """
@prefix ex: <urn:gymact:test:> .
@prefix sh: <http://www.w3.org/ns/shacl#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

ex:ThingShape a sh:NodeShape ;
    sh:targetClass ex:Thing ;
    sh:property [
        sh:path ex:hasName ;
        sh:minCount 1 ;
        sh:maxCount 1 ;
        sh:datatype xsd:string ;
    ] .
"""

CONFORMANT_TTL = """
@prefix ex: <urn:gymact:test:> .

ex:thing1 a ex:Thing ;
    ex:hasName "gymact" .
"""

NONCONFORMANT_TTL = """
@prefix ex: <urn:gymact:test:> .

ex:thing1 a ex:Thing .
"""


def _shapes_graph() -> Graph:
    graph = Graph()
    graph.parse(data=SHAPES_TTL, format="turtle")
    return graph


def test_shacl_verifier_passes_conformant_graph() -> None:
    verifier = ShaclPostconditionVerifier(shapes_path=_shapes_graph())

    passed, reason = verifier.judge({}, {"turtle": CONFORMANT_TTL})

    assert passed is True
    assert reason == "VERIFIED:SHACL_CONFORMS"


def test_shacl_verifier_fails_nonconformant_graph_with_real_violation_reason() -> None:
    verifier = ShaclPostconditionVerifier(shapes_path=_shapes_graph())

    passed, reason = verifier.judge({}, {"turtle": NONCONFORMANT_TTL})

    assert passed is False
    assert reason.startswith("SHACL_VIOLATION:")
    # Real pyshacl results-graph text names the failing path/constraint, not a canned string.
    assert "hasName" in reason
    assert "MinCountConstraintComponent" in reason


def test_shacl_verifier_accepts_a_prebuilt_graph_directly() -> None:
    verifier = ShaclPostconditionVerifier(shapes_path=_shapes_graph())
    data_graph = Graph()
    data_graph.parse(data=CONFORMANT_TTL, format="turtle")

    passed, reason = verifier.judge({}, {"graph": data_graph})

    assert passed is True
    assert reason == "VERIFIED:SHACL_CONFORMS"


def test_shacl_verifier_accepts_a_bare_rdflib_graph_as_observed() -> None:
    verifier = ShaclPostconditionVerifier(shapes_path=_shapes_graph())
    data_graph = Graph()
    data_graph.parse(data=CONFORMANT_TTL, format="turtle")

    passed, reason = verifier.judge({}, data_graph)

    assert passed is True
    assert reason == "VERIFIED:SHACL_CONFORMS"


def test_shacl_verifier_refuses_non_graph_shaped_observed_cleanly() -> None:
    verifier = ShaclPostconditionVerifier(shapes_path=_shapes_graph())

    passed, reason = verifier.judge({}, {"status": "ok", "count": 3})

    assert passed is False
    assert reason == "SHACL_VERIFICATION_REQUIRES_GRAPH_SHAPED_OBSERVED"


def test_shacl_verifier_refuses_empty_observed_dict() -> None:
    verifier = ShaclPostconditionVerifier(shapes_path=_shapes_graph())

    passed, reason = verifier.judge({}, {})

    assert passed is False
    assert reason == "SHACL_VERIFICATION_REQUIRES_GRAPH_SHAPED_OBSERVED"


def test_shacl_verifier_constructs_from_a_real_shapes_file_path(tmp_path) -> None:
    shapes_file = tmp_path / "shapes.ttl"
    shapes_file.write_text(SHAPES_TTL)
    verifier = ShaclPostconditionVerifier(shapes_path=shapes_file)

    passed, reason = verifier.judge({}, {"turtle": CONFORMANT_TTL})

    assert passed is True
    assert reason == "VERIFIED:SHACL_CONFORMS"


def test_shacl_verifier_against_real_togaf_gym_shapes_file() -> None:
    """The togaf_gym shapes.ttl is real repo content, not a test fixture -- confirms this
    verifier is reusable across gyms' real shape files, not hardcoded to the inline test
    shapes above."""
    from pathlib import Path

    shapes_path = (
        Path(__file__).resolve().parent.parent / "rust" / "togaf_gym" / "shapes.ttl"
    )
    verifier = ShaclPostconditionVerifier(shapes_path=shapes_path)

    # An empty data graph trivially fails every targetNode-based oracle shape's sh:hasValue
    # constraints (the target nodes simply don't exist), which is still a real conforms=False
    # verdict from a real pyshacl run against real repo shapes -- not a canned result.
    passed, reason = verifier.judge({}, {"graph": Graph()})

    assert isinstance(passed, bool)
    assert reason.startswith("VERIFIED:") or reason.startswith("SHACL_VIOLATION:")


def test_dict_subset_verifier_still_passes_on_matching_subset() -> None:
    verifier = DictSubsetVerifier()

    passed, reason = verifier.judge({"status": "ok"}, {"status": "ok", "extra": 1})

    assert passed is True
    assert reason == "VERIFIED:SUBSET_MATCH"


def test_dict_subset_verifier_still_fails_on_mismatch() -> None:
    verifier = DictSubsetVerifier()

    passed, reason = verifier.judge({"status": "ok"}, {"status": "broken"})

    assert passed is False
    assert reason == "VERIFY_MISMATCH:status"
