"""W603: the gymact AIRo risk description parses and stays grounded.

Lane W603, AIRo wiring wave. Validates
src/gymact/ontology/airo_risk_description.ttl.
"""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
TTL_PATH = REPO_ROOT / "src/gymact/ontology/airo_risk_description.ttl"

AIRO = "https://w3id.org/airo#"

CITED_TEST_FILES = [
    "tests/test_production_surfaces.py",
    "tests/test_gymnasium_env.py",
    "tests/test_two_gym_gate.py",
    "tests/test_standing_enforcement.py",
]

# Cited files must exist BEFORE anything else — grounding is the point.
def test_cited_test_files_exist():
    missing = [p for p in CITED_TEST_FILES if not (REPO_ROOT / p).exists()]
    assert missing == [], f"cited test files missing on disk: {missing}"


def test_ttl_exists_and_prefixes_declared():
    text = TTL_PATH.read_text()
    for prefix in ("airo:", "dcterms:", "rdfs:", "xsd:"):
        assert f"@prefix {prefix}" in text, f"missing @prefix {prefix}"
    assert AIRO in text


def _load_graph():
    rdflib = __import__("rdflib")
    g = rdflib.Graph()
    g.parse(str(TTL_PATH), format="turtle")
    return g


def test_rdflib_parse_and_airo_structure():
    rdflib = __import__("rdflib")
    try:
        g = _load_graph()
    except ImportError:
        import pytest

        pytest.skip("rdflib not installed")
        return
    from rdflib import Namespace, RDF

    airo = Namespace(AIRO)
    system = rdflib.URIRef("https://gymact.example/airo/#gymact-system")
    assert (system, RDF.type, airo.AISystem) in g
    assert (system, airo.isDeployedBy, None) in g
    deployer_type = next(g.objects(system, airo.isDeployedBy), None)
    if deployer_type is not None:
        assert (deployer_type, RDF.type, airo.AIDeployer) in g
    risks = list(g.objects(system, airo.hasRisk))
    assert len(risks) >= 3
    for risk in risks:
        assert (risk, RDF.type, airo.Risk) in g
        assert (risk, airo.hasConsequence, None) in g
        assert (risk, airo.hasLikelihood, None) in g
        assert (risk, airo.hasSeverity, None) in g
        for cons in g.objects(risk, airo.hasConsequence):
            assert (cons, RDF.type, airo.Consequence) in g
            assert any(
                (cons, airo.hasImpact, impact) in g
                for impact in g.objects(cons, airo.hasImpact)
            )
        for src in g.subjects(airo.isRiskSourceFor, risk):
            assert (src, RDF.type, airo.RiskSource) in g
    controls = list(g.subjects(RDF.type, airo.RiskControl))
    assert len(controls) >= 2
    # every control is attached to at least one risk
    for ctrl in controls:
        assert any(
            (risk, airo.hasRiskControl, ctrl) in g
            for risk in risks
        ), f"control {ctrl} not attached to any risk"


def test_minimal_turtle_sanity_without_rdflib():
    """Fallback structural check: quotes/brackets balance per statement."""
    text = TTL_PATH.read_text()
    # strip comments and string literals before counting braces
    import re

    stripped = re.sub(r"#[^\n]*", "", text)
    stripped = re.sub(r'"(?:[^"\\]|\\.)*"', '""', stripped)
    assert stripped.count("[") == stripped.count("]")
    assert stripped.count("{") == stripped.count("}")
    assert stripped.count(")") == stripped.count("(")
    assert text.count('"') % 2 == 0
    # every non-comment, non-prefix statement ends with '.' or ','
    body = [
        line.strip()
        for line in stripped.splitlines()
        if line.strip() and not line.strip().startswith("@")
    ]
    assert body, "no statements found"
