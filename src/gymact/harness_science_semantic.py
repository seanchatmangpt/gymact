"""Public-ontology projection for GymAct harness-science evidence.

Local IRIs are ABox resources or SKOS concepts only. PROV-O, P-PLAN, SOSA,
EARL, DQV, ODRL and DCTERMS carry the semantics; this module grants no DO authority.
"""

from __future__ import annotations

from typing import Final

from rdflib import BNode, Graph, Literal, Namespace, RDF, URIRef
from rdflib.namespace import DCTERMS, PROV, SKOS

from gymact.harness_science import (
    PAPER_IRIS,
    ConfigurationEffect,
    HarnessAuditResult,
    HarnessScienceSnapshot,
    HypothesisEvaluation,
    LifecycleScorecard,
    ProcessScorecard,
    TrajectoryAudit,
)

PPLAN: Final = Namespace("http://purl.org/net/p-plan#")
SOSA: Final = Namespace("http://www.w3.org/ns/sosa/")
EARL: Final = Namespace("http://www.w3.org/ns/earl#")
DQV: Final = Namespace("http://www.w3.org/ns/dqv#")
ODRL: Final = Namespace("http://www.w3.org/ns/odrl/2/")
HS: Final = Namespace("urn:gymact:harness-science:")


def _source(graph: Graph, subject: URIRef, paper: str) -> None:
    graph.add((subject, DCTERMS.source, URIRef(PAPER_IRIS[paper])))


def _concept(graph: Graph, name: str, label: str, paper: str) -> URIRef:
    concept = HS[name]
    graph.add((concept, RDF.type, SKOS.Concept))
    graph.add((concept, SKOS.prefLabel, Literal(label)))
    _source(graph, concept, paper)
    return concept


def _measurement(graph: Graph, activity: URIRef, metric: URIRef, value: object) -> None:
    node = BNode()
    graph.add((node, RDF.type, DQV.QualityMeasurement))
    graph.add((node, DQV.isMeasurementOf, metric))
    graph.add((node, DQV.value, Literal(value)))
    graph.add((node, PROV.wasGeneratedBy, activity))


def configuration_effect_graph(effect: ConfigurationEffect, *, run_iri: str) -> Graph:
    graph = Graph()
    run = URIRef(run_iri)
    observation = HS[f"configuration-effect-{run_iri.rsplit(':', 1)[-1]}"]
    axis = _concept(graph, f"axis-{effect.axis.value}", effect.axis.value, "agentcompass")
    graph.add((run, RDF.type, PROV.Activity))
    graph.add((observation, RDF.type, SOSA.Observation))
    graph.add((observation, SOSA.observedProperty, axis))
    result = BNode()
    graph.add((result, RDF.type, SOSA.Result))
    graph.add((result, PROV.value, Literal(effect.delta)))
    graph.add((observation, SOSA.hasResult, result))
    graph.add((observation, PROV.wasGeneratedBy, run))
    _source(graph, observation, "harness_bench")
    graph.add((observation, DCTERMS.references, URIRef(PAPER_IRIS["agentcompass"])))
    graph.add(
        (observation, DCTERMS.references, URIRef(PAPER_IRIS["rethinking_harness_evolution"]))
    )
    return graph


def process_graph(scorecard: ProcessScorecard, *, run_iri: str) -> Graph:
    graph = Graph()
    run = URIRef(run_iri)
    graph.add((run, RDF.type, PROV.Activity))
    control_metric = _concept(
        graph, "metric-control-preservation", "control preservation", "procctrlbench"
    )
    _measurement(graph, run, control_metric, scorecard.control.score)
    for index, finding in enumerate(scorecard.findings):
        assertion = URIRef(f"{run_iri}:process-finding:{index}")
        result = BNode()
        graph.add((assertion, RDF.type, EARL.Assertion))
        graph.add((assertion, EARL.test, HS[f"process-defect-{finding.defect_type}"]))
        graph.add((assertion, EARL.result, result))
        graph.add((assertion, PROV.used, URIRef(finding.evidence_ref)))
        graph.add((result, RDF.type, EARL.TestResult))
        graph.add((result, EARL.outcome, EARL.failed))
        _source(graph, assertion, "procctrlbench")
    return graph


def trajectory_graph(audit: TrajectoryAudit, *, run_iri: str) -> Graph:
    graph = Graph()
    run = URIRef(run_iri)
    graph.add((run, RDF.type, PROV.Activity))
    safe_metric = _concept(graph, "metric-trajectory-safe", "trajectory safety", "she")
    control_metric = _concept(graph, "metric-trajectory-control", "trajectory control", "she")
    _measurement(graph, run, safe_metric, audit.safe)
    _measurement(graph, run, control_metric, audit.control_preserved)
    for event in audit.events:
        event_ref = URIRef(event.evidence_ref)
        graph.add((event_ref, RDF.type, PROV.Entity))
        graph.add((run, PROV.used, event_ref))
    return graph


def harness_audit_graph(audit: HarnessAuditResult, *, run_iri: str) -> Graph:
    graph = Graph()
    run = URIRef(run_iri)
    graph.add((run, RDF.type, PROV.Activity))
    for name, value in (
        ("boundary-compliance", audit.boundary_compliance),
        ("execution-fidelity", audit.execution_fidelity),
        ("system-stability", audit.system_stability),
    ):
        metric = _concept(graph, f"metric-{name}", name, "harness_audit")
        _measurement(graph, run, metric, value)
    for evidence_ref in audit.hidden_evidence_refs:
        graph.add((run, PROV.used, URIRef(evidence_ref)))
    return graph


def lifecycle_graph(scorecard: LifecycleScorecard, *, run_iri: str) -> Graph:
    graph = Graph()
    run = URIRef(run_iri)
    graph.add((run, RDF.type, PROV.Activity))
    policy = URIRef(f"{run_iri}:lifecycle-safety-policy")
    graph.add((policy, RDF.type, ODRL.Policy))
    _source(graph, policy, "harnessrisk")
    for key, value in (
        ("utility", scorecard.utility),
        ("attack-success-rate", scorecard.attack_success_rate),
        ("persistence", scorecard.persistence),
        ("detection", scorecard.detection),
    ):
        if value is None:
            continue
        metric = _concept(graph, f"metric-{key}", key, "harnessrisk")
        _measurement(graph, run, metric, value)
    return graph


def hypothesis_graph(evaluation: HypothesisEvaluation, *, run_iri: str) -> Graph:
    graph = Graph()
    run = URIRef(run_iri)
    assertion = URIRef(f"{run_iri}:hypothesis:{evaluation.change_id}")
    result = BNode()
    graph.add((run, RDF.type, PROV.Activity))
    graph.add((assertion, RDF.type, EARL.Assertion))
    graph.add((assertion, EARL.result, result))
    graph.add((result, RDF.type, EARL.TestResult))
    outcome = EARL.passed if evaluation.standing.value == "SUPPORTED" else EARL.failed
    if evaluation.standing.value == "INCONCLUSIVE":
        outcome = EARL.untested
    graph.add((result, EARL.outcome, outcome))
    graph.add((result, DCTERMS.description, Literal(evaluation.reason)))
    _source(graph, assertion, "ahe")
    return graph


def snapshot_graph(snapshot: HarnessScienceSnapshot, *, run_iri: str) -> Graph:
    graph = Graph()
    bundle = HS[f"snapshot-{snapshot.fingerprint}"]
    graph.add((bundle, RDF.type, PROV.Bundle))
    graph.add((bundle, DCTERMS.identifier, Literal(snapshot.fingerprint)))
    for paper in PAPER_IRIS.values():
        graph.add((bundle, DCTERMS.references, URIRef(paper)))
    run = URIRef(run_iri)
    graph.add((run, RDF.type, PROV.Activity))
    graph.add((bundle, PROV.wasGeneratedBy, run))
    for evidence_ref in snapshot.evidence_refs:
        graph.add((run, PROV.used, URIRef(evidence_ref)))
    return graph
