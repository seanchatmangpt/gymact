"""W677: AIRo wiring pin — deepening of the W603 structure court.

Asserts the full AIRo risk-description surface for gymact
(src/gymact/ontology/airo_risk_description.ttl) against the AIRO 1.0
vocabulary via real rdflib parses — no mocks, real graph state.
"""

from pathlib import Path

import pytest
import rdflib
from rdflib import Namespace, RDF, RDFS

REPO_ROOT = Path(__file__).resolve().parents[1]
TTL_PATH = REPO_ROOT / "src/gymact/ontology/airo_risk_description.ttl"
AIRO = "https://w3id.org/airo#"

# Refusal-atom -> risk-concept mapping pinned exactly as authored in W603.
RISK_SOURCE_TO_RISK = {
    "#rs-environment-nondeterminism": "#risk-nondeterminism",
    "#rs-reward-hacking": "#risk-reward-hacking",
    "#rs-evaluator-gaming": "#risk-evaluator-gaming",
}

def _load_graph() -> rdflib.Graph:
    g = rdflib.Graph()
    g.parse(str(TTL_PATH), format="turtle")
    return g


@pytest.fixture(scope="module")
def graph() -> rdflib.Graph:
    return _load_graph()


def test_ttl_present_and_size_bounded():
    assert TTL_PATH.exists()
    text = TTL_PATH.read_text()
    assert 5000 <= len(text.encode()) <= 20000  # ledger row: 5,353 B


@pytest.mark.parametrize("base", RISK_SOURCE_TO_RISK.values())
def test_every_risk_declared(graph, base):
    system = rdflib.URIRef("https://gymact.example/airo/#gymact-system")
    risks = {str(o) for o in graph.objects(system, Namespace(AIRO).hasRisk)}
    assert "https://gymact.example/airo/" + base in risks


def test_risk_source_to_risk_mapping(graph):
    """Refusal-atom -> risk-concept table: each RiskSource maps via
    airo:isRiskSourceFor to exactly one declared Risk, and every Risk
    has a RiskSource."""
    airo = Namespace(AIRO)
    base = "https://gymact.example/airo/"
    risks = set(graph.subjects(RDF.type, airo.Risk))
    sources = set(graph.subjects(RDF.type, airo.RiskSource))
    assert len(risks) == 3
    assert len(sources) == 3
    for src, risk in RISK_SOURCE_TO_RISK.items():
        s = rdflib.URIRef(base + src)
        r = rdflib.URIRef(base + risk)
        assert s in sources
        assert (s, airo.isRiskSourceFor, r) in graph
    # no dangling risk sources
    for s in sources:
        assert len(list(graph.objects(s, airo.isRiskSourceFor))) == 1


def test_every_risk_has_consequence_control_likelihood_severity(graph):
    airo = Namespace(AIRO)
    for r in graph.subjects(RDF.type, airo.Risk):
        assert next(graph.objects(r, airo.hasConsequence), None) is not None
        assert next(graph.objects(r, airo.hasRiskControl), None) is not None
        assert next(graph.objects(r, airo.hasLikelihood), None) is not None
        assert next(graph.objects(r, airo.hasSeverity), None) is not None


def test_risk_controls_cite_real_files(graph):
    """Risk controls must cite test files that actually exist on disk."""
    airo = Namespace(AIRO)
    dcterms = Namespace("http://purl.org/dc/terms/")
    cited = set()
    for rc in graph.subjects(RDF.type, airo.RiskControl):
        desc = next(graph.objects(rc, dcterms.description), None)
        assert desc is not None, f"risk control {rc} lacks dcterms:description"
        for token in str(desc).split():
            for path in token.split("("):
                for p in path.split(")"):
                    if p.startswith("tests/"):
                        cited.add(p)
    assert cited, "no test-file citations found in risk controls"
    missing = [p for p in cited if not (REPO_ROOT / p).exists()]
    assert missing == [], f"risk controls cite missing files: {missing}"


def test_qualitative_estimates_disclosed(graph):
    """Likelihood/Severity nodes must be labeled as structured estimates,
    not measurements (no-overclaiming pin)."""
    airo = Namespace(AIRO)
    for cls in (airo.Likelihood, airo.Severity):
        nodes = list(graph.subjects(RDF.type, cls))
        assert nodes
        for n in nodes:
            label = next(graph.objects(n, RDFS.label), None)
            assert label is not None
            assert "structured estimate" in str(label)
            assert "not a measurement" in str(label)


def test_deployer_edge(graph):
    airo = Namespace(AIRO)
    system = rdflib.URIRef("https://gymact.example/airo/#gymact-system")
    operator = rdflib.URIRef("https://gymact.example/airo/#operator")
    assert (system, airo.isDeployedBy, operator) in graph
    assert (operator, RDF.type, airo.AIDeployer) in graph
    assert (system, RDF.type, airo.AISystem) in graph
